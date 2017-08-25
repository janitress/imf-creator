from imfcreator.mainapplication import MainApplication
from imfcreator.imf.constants import *
from imfcreator.imf.player import ImfPlayer
from imfcreator.imf.imfmusicfile import ImfMusicFile
from imfcreator.signal import Signal
import inspect
import time
import Tix as tix
from imfcreator.midi.reader import MidiReader, MidiEvent
import mido
import math
import timeit


# class Signal:
#     """A simple event system.
#
#     Based on: https://stackoverflow.com/posts/35957226/revisions
#     """
#     def __init__(self, **args):
#         self._args = args
#         self._argnames = set(args.keys())
#         self._listeners = []
#
#     def _args_string(self):
#         return ", ".join(sorted(self._argnames))
#
#     def __iadd__(self, listener):
#         args = inspect.getargspec(listener).args
#         if set(n for n in args) != self._argnames:
#             raise ValueError("Listener must have these arguments: {}".format(self._args_string()))
#         self._listeners.append(listener)
#         return self
#
#     def __isub__(self, listener):
#         self._listeners.remove(listener)
#         return self
#
#     def __call__(self, *args, **kwargs):
#         if args or set(kwargs.keys()) != self._argnames:
#             raise ValueError("This Signal requires these arguments: {}".format(self._args_string()))
#         for listener in self._listeners:
#             listener(**kwargs)


def listener1(x, y):
    print("method listener: {}, {}".format(x, y))


def listener2(x, y):
    print("lambda listener: {}, {}".format(x, y))

def listener3():
    print("no args")


def main(imf):
    # player = ImfPlayer()
    # file_info = player.load("test.wlf")
    # # file_info = player.load("wolf3d.wlf")
    # print(file_info)
    # # print("num_commands: {}".format(player.num_commands))
    # # player.mute[1] = True
    # # player.mute[2] = True
    # # player.mute[3] = True
    # # player.mute[4] = True
    # # player.mute[5] = True
    # # player.mute[6] = True
    # # player.mute[7] = True
    # # player.mute[8] = True
    # # player.seek(200)
    # # player.play(True)
    # while player.isactive:
    #     # print("isactive")
    #     time.sleep(0.1)
    # player.close()
    root = MainApplication()
    root.player.set_song(imf)
    root.mainloop()

def testsignals():
    changed = Signal(x=int, y=int)
    changed += listener1
    changed += lambda x, y: listener2(x, y)
    changed(x=23, y=13)
    changed = Signal()
    changed += listener3
    changed()


def miditest(filename):
    # filename = "testfmt0.mid"
    # filename = "testfmt1.mid"
    # filename = "brahms_opus1_1.mid"
    reader = MidiReader()
    reader.load(filename)
    for track in reader.tracks:
        if not track.number in [7, 8]:
            continue
        print '=== Track: {}'.format(track.name)
        for message in track:
            print "  " + str(message)
    # midi_file = mido.MidiFile(filename)
    # for track in midi_file.tracks:
    #     print '=== Track {}'
    #     for message in track:
    #         print '  {!r} = {}'.format(message.__class__.__name__, message.__dict__)


import copy

def sort_midi(midi): #, mute_tracks=None, mute_channels=None):
    # Combine all tracks into one track.
    events = []
    for track in midi.tracks:
        time = 0
        for event in track:
            time += event.delta
            del event.delta
            event = copy.copy(event)
            event.event_time = time
            event.track = track.number
            events.append(event)
    # if mute_tracks:
    #     events = filter(lambda event: event.track not in mute_tracks, events)
    # if mute_channels:
    #     events = filter(lambda event: not hasattr(event, "channel") or event.channel not in mute_channels, events)
    # Sort by event time and channel. Note-on events with a velocity should come last at a given time within the song.
    events = sorted(events, key=lambda event: (
        event.event_time,
        1 if event.type == "note_on" and event.velocity > 0 else 0,
        event.channel if hasattr(event, "channel") else -1,
    ))
    return events

# def add_command(regs, reg, value, ticks):


def convert_midi_to_imf(midi, instruments, mute_tracks=None, mute_channels=None):
    events = sort_midi(midi) #, mute_tracks, mute_channels)
    imf = ImfMusicFile()
    # Prepare MIDI and IMF channel variables.
    midi_channels = {}
    for ch in range(16):
        midi_channels[ch] = {
            "instrument": None,
            "volume": 127,
            "pitch_bend": 0,
            "scaled_pitch_bend": 0.0,
            "active_notes": [],
        }
    imf_channels = [{
        "id": channel,
        "instrument": None,
        "last_note": None,
    } for channel in range(1, 9)]
    regs = [None] * 256
    midi_tempo = 120.0

    # Define helper functions.
    def calc_imf_ticks(value):
        return int(imf.ticks_per_second * (float(value) / midi.division) * (60.0 / midi_tempo))

    def find_imf_channel(instrument, note):
        channel = filter(lambda ch: ch["instrument"] == instrument and ch["last_note"] is None, imf_channels)
        if channel:
            return channel[0]  #["id"]
        channel = filter(lambda ch: ch["last_note"] is None, imf_channels)
        if channel:
            return channel[0]  #["id"]
        # TODO Aggressive channel find.
        return None

    def add_commands(commands):
        added_command = False
        for command in commands:
            reg, value = command
            # if (reg & 0x20) == 0x20:
            #     value = (value & 0xf0) | 1
            if regs[reg] != value:
                imf.add_command(reg, value, 0)
                regs[reg] = value
                added_command = True
        return added_command

    def get_block_and_freq(note, scaled_pitch_bend):
        assert note < 128
        while note >= len(BLOCK_FREQ_NOTE_MAP):
            note -= 12
        block, freq = BLOCK_FREQ_NOTE_MAP[note]
        # Adjust for pitch bend.
        # The octave adjustment relies heavily on how the BLOCK_FREQ_NOTE_MAP has been calculated.
        # F% is close to the top of the 1023 limit while G is in the middle at 517. Because of this,
        # bends that cross over the line between F# and G are better handled in the range below G and the
        # lower block/freq is adjusted upward so that it is in the same block as the other note.
        # For each increment of 1 to the block, the f-num needs to be halved.  This can lead to a loss of
        # precision, but hopefully it won't be too drastic.
        if scaled_pitch_bend < 0:
            semitones = int(math.floor(scaled_pitch_bend))
            bend_block, bend_freq = BLOCK_FREQ_NOTE_MAP[note - semitones]
            # If the bend-to note is on a lower block/octave, multiply the bend-to f-num by 0.5 per block
            # to bring it up to the same block as the original note.
            if bend_block < block:
                bend_freq = bend_freq / (2.0 ** (block - bend_block))
            freq = int(freq - (freq - bend_freq) * scaled_pitch_bend / -semitones)
        elif scaled_pitch_bend > 0:
            semitones = int(math.ceil(scaled_pitch_bend))
            bend_block, bend_freq = BLOCK_FREQ_NOTE_MAP[note + semitones]
            # If the bend-to note is on a higher block/octave, multiple the original f-num by 0.5 per block
            # to bring it up to the same block as the bend-to note.
            if bend_block > block:
                freq = freq / (2.0 ** (bend_block - block))
                block = bend_block
            freq = int(freq + (bend_freq - freq) * scaled_pitch_bend / semitones)
        assert 0 <= block <= 7
        assert 0 <= freq <= 0x3ff
        return block, freq

    def find_imf_channel_for_instrument_note(instrument, note):
        channel = filter(lambda ch: ch["instrument"] == instrument and ch["last_note"] == note, imf_channels)
        if channel:
            return channel[0]
        return None

    def note_off(event):
        commands = []
        inst_num, note = get_inst_and_note(event, False)
        channel = find_imf_channel_for_instrument_note(inst_num, note)
        if channel:
            channel["last_note"] = None
            # block, freq = get_block_and_freq(event)
            commands += [
                # (BLOCK_MSG | channel["id"], KEY_OFF_MASK | (block << 2) | (freq >> 8)),
                (BLOCK_MSG | channel["id"], KEY_OFF_MASK),
            ]
        # else:
        #     print "Could not find note to shut off! inst: {}, note: {}".format(inst_num, note)
        return commands

    def get_inst_and_note(event, is_note_on, voice=0):
        if event.channel == 9:
            inst_num = 128 + event.note - 35
            note = instruments[inst_num].given_note
        else:
            midi_track = midi_channels[event.channel]
            if midi_track["instrument"] is None:
                print "No instrument assigned to track {}, defaulting to 0."
                midi_track["instrument"] = 0
            inst_num = midi_track["instrument"]
            note = event.note
            note += instruments[inst_num].note_offset[voice]
            if note < 0 or note > 127:
                print "Note out of range: {}".format(note)
                note = 60
            if is_note_on:
                midi_track["active_notes"].append({
                    "note": note,
                    "inst_num": inst_num,
                    "event": event,
                })
            else:
                # match = midi_track["notes"].get(event.note)
                match = filter(lambda note_info: note_info["event"].note == event.note, midi_track["active_notes"])
                if match:
                    match = match[0]
                    note = match["note"]
                    inst_num = match["inst_num"]
                    midi_track["active_notes"].remove(match)
                else:
                    print "Tried to remove non-active note: track {}, inst {} note {}".format(event.track, inst_num, note)
        return inst_num, note

    def note_on(event):
        commands = []
        voice = 0
        midi_track = midi_channels[event.channel]
        inst_num, note = get_inst_and_note(event, True)
        channel = find_imf_channel(inst_num, note)
        if channel:
            # Check for instrument change.
            instrument = instruments[inst_num]
            if channel["instrument"] != inst_num:
                commands += instrument.get_regs(channel["id"], voice)
                channel["instrument"] = inst_num
            volume = int(midi_track["volume"] * event.velocity / 127.0)
            channel["last_note"] = note
            block, freq = get_block_and_freq(note, midi_track["scaled_pitch_bend"])
            commands += [
                (
                    VOLUME_MSG | CARRIERS[channel["id"]],
                    ((127 - volume) / 2) | instrument.carrier[voice].key_scale_level
                ),
                (FREQ_MSG | channel["id"], freq & 0xff),
                (BLOCK_MSG | channel["id"], KEY_ON_MASK | (block << 2) | (freq >> 8)),
            ]
        # else:
        #     print "Could not find channel for note on! inst: {}, note: {}".format(inst_num, note)
        return commands

    def pitch_bend(event):
        commands = []
        amount = event.value - event.value % pitch_bend_resolution
        if midi_channels[event.channel]["pitch_bend"] != amount:
            midi_channels[event.channel]["pitch_bend"] = amount
            # Scale picth bend to -1..1
            scaled_pitch_bend = amount / -pitch_bend_range[0] if amount < 0 else amount / pitch_bend_range[1]
            scaled_pitch_bend *= 2  # TODO Read from controller messages. 2 semi-tones is the default.
            midi_channels[event.channel]["scaled_pitch_bend"] = scaled_pitch_bend
            instrument = midi_channels[event.channel]["instrument"]
            for note_info in midi_channels[event.channel]["active_notes"]:
                note = note_info["note"]
                channel = find_imf_channel_for_instrument_note(instrument, note)
                if channel:
                    block, freq = get_block_and_freq(note, scaled_pitch_bend)
                    commands += [
                        (FREQ_MSG | channel["id"], freq & 0xff),
                        (BLOCK_MSG | channel["id"], KEY_ON_MASK | (block << 2) | (freq >> 8)),
                    ]
                    pass
        return commands

    def adjust_volume(event):
        commands = []
        voice = 0
        midi_track = midi_channels[event.channel]
        midi_track["volume"] = event.value
        inst_num = midi_track["instrument"]
        for note_info in midi_track["active_notes"]:
            channel = find_imf_channel_for_instrument_note(inst_num, note_info["note"])
            if channel:
                volume = int(midi_track["volume"] * note_info["event"].velocity / 127.0)
                instrument = instruments[inst_num]
                commands += [
                    (
                        VOLUME_MSG | CARRIERS[channel["id"]],
                        ((127 - volume) / 2) | instrument.carrier[voice].key_scale_level
                    ),
                ]
        return commands

    # Cycle MIDI events and convert to IMF commands.
    last_ticks = 0
    # ticks = 0
    pitch_bend_resolution = 0x200
    pitch_bend_range = (-8192.0 - -8192 % -pitch_bend_resolution, 8191.0 - 8191 % pitch_bend_resolution)
    imf.commands.append((0, 0, 0)) # Always start with 0, 0, 0
    for event in events:
        ticks = calc_imf_ticks(event.event_time - last_ticks)
        if ticks > 0:
            prev_ticks = imf.commands[-1][2] + ticks
            imf.commands[-1] = imf.commands[-1][:2] + (prev_ticks,)
            last_ticks = event.event_time #ticks
        # Perform muting
        if mute_tracks:
            if event.track in mute_tracks:
                continue
        if mute_channels:
            if hasattr(event, "channel") and event.channel in mute_channels:
                continue
        # Handle events.
        commands = []  # list of (reg, value) tuples.
        if (event.type == "note_on" and event.velocity == 0) or event.type == "note_off":
            commands += note_off(event)
        elif event.type == "note_on":
            commands += note_on(event)
        elif event.type == "controller_change" and event.controller == 7:  # volume, TODO: .controller_name
            commands += adjust_volume(event)
        elif event.type == "pitch_bend":
            commands += pitch_bend(event)
        elif event.type == "program_change":
            midi_channels[event.channel]["instrument"] = event.program
        elif event.type == "meta" and event.meta_type == "set_tempo":
            midi_tempo = float(event.bpm)
        add_commands(commands)
    imf._save("output.wlf", file_type=0)
    # for command in imf.commands:
    #     print(map(hex, command))
    for mc in range(16):
        if midi_channels[mc]["active_notes"]:
            print "midi track {} had open notes: {}".format(mc, midi_channels[mc]["active_notes"])
    for ch in imf_channels:
        if ch["last_note"]:
            print "imf channel {} had open note: {}".format(ch["id"], ch["last_note"])
    return imf




from imfcreator.adlib import instrumentfile
instruments = instrumentfile.get_all_instruments("GENMIDI.OP2")


reader = MidiReader()
reader.load("ghostbusters.mid")
# reader.load("test-pitchbend.mid")
imf = convert_midi_to_imf(reader, instruments) #, mute_channels=[9])
# imf = convert_midi_to_imf(reader, instruments, mute_tracks=[1], mute_channels=[9])
# convert_midi_to_imf(reader, instruments, mute_tracks=[3])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2], mute_channels=[9])

main(imf)
# testsignals()
# miditest("Ghostbusters.mid")
