from .constants import *
import struct

_META_TYPE_NAMES = {
    0: 'sequence_number',
    1: 'text_event',
    2: 'copyright',
    3: 'track_name',
    4: 'instrument_name',
    5: 'lyric',
    6: 'marker',
    7: 'cue_point',
    0x20: 'channel_prefix',
    0x2f: 'end_of_track',
    0x51: 'set_tempo',
    0x54: 'smtpe_offset',
    0x58: 'time_signature',
    0x59: 'key_signature',
    0x7f: 'sequencer_specific',
}
# TODO
# http://www.indiana.edu/~emusic/cntrlnumb.html
# http://nickfever.com/music/midi-cc-list
# _CONTROLLER_NAMES = {
#     7: "volume",
# }
# http://www.2writers.com/eddie/TutNrpn.htm - pitch bend, rpn
# https://www.midikits.net/midi_analyser/pitch_bend.htm




class MidiEvent:
    """Represents an abstract event within a MIDI file."""
    def __init__(self, **kwargs):
        if kwargs.get("delta") is None:
            raise Exception("A value for \"delta\" is required.")
        if kwargs.get("type") is None:
            raise Exception("A value for \"type\" is required.")
        for k, v in kwargs.iteritems():
            self.__dict__[k] = v

    def __repr__(self):
        return str(self.__dict__)

    @classmethod
    def create_event(cls, delta, event_type, stream):
        args = {
            "delta": delta
        }
        if event_type == F0_SYSEX_EVENT:
            data_length = stream._read_var_length()
            args.update({
                "type": "f0_sysex",
                "data": [stream._next_byte() for x in range(data_length)],
            })
        elif event_type == F7_SYSEX_EVENT:
            data_length = stream._read_var_length()
            args.update({
                "type": "f7_sysex",
                "data": [stream._next_byte() for x in range(data_length)],
            })
        elif event_type == META_EVENT:
            args["type"] = "meta"
            meta_type = stream._next_byte()
            meta_type_name = _META_TYPE_NAMES.get(meta_type)
            if meta_type_name is None:
                meta_type_name = "unknown_0x{:x}".format((meta_type))
            args["meta_type"] = meta_type_name
            data_length = stream._read_var_length()
            if meta_type_name in [
                "text_event",
                "copyright",
                "track_name",
                "instrument_name",
                "lyric",
                "marker",
                "cue_point"]:
                args["text"] = stream.f.read(data_length)
            elif meta_type_name == "set_tempo":
                args["speed"] = (stream._next_byte() << 16) + (stream._next_byte() << 8) + stream._next_byte()
                args["bpm"] = 60000000 / args["speed"]  # 60 seconds as microseconds
            elif meta_type_name == "smtpe_offset":
                args.update({
                    "hours": stream._next_byte(),
                    "minutes": stream._next_byte(),
                    "seconds": stream._next_byte(),
                    "frames": stream._next_byte(),
                    "fractional_frames": stream._next_byte(),
                })
            elif meta_type_name == "time_signature":
                args.update({
                    "numerator": stream._next_byte(),
                    "denominator": 2 ** stream._next_byte(),  # given in powers of 2.
                    "midi_clocks_per_metronome_tick": stream._next_byte(),
                    "number_of_32nd_notes_per_beat": stream._next_byte(),  # almost always 8
                })
            elif meta_type_name == "key_signature":
                keys = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#", "G#", "D#", "A#"]
                sharps_flats, major_minor = struct.unpack("<bB", stream.f.read(2))
                args["key"] = keys[sharps_flats + 7 + major_minor * 3] + "m" * major_minor
            # elif meta_type_name == "sequencer_specific":
            #     # TODO Convert data.
            #       id      1 or 3 bytes representing the Manufacturer's ID
            #       data    binary data
            else:
                if data_length:
                    args["data"] = [stream._next_byte() for x in range(data_length)],
        else:
            args["channel"] = event_type & 0xf
            event_type &= 0xf0
            if event_type == NOTE_OFF_EVENT:
                args.update({
                    "type": "note_off",
                    "note": stream._next_byte(),
                    "velocity": stream._next_byte(),
                })
            elif event_type == NOTE_ON_EVENT:
                args.update({
                    "type": "note_on",
                    "note": stream._next_byte(),
                    "velocity": stream._next_byte(),
                })
            elif event_type == POLYPHONIC_KEY_PRESSURE_EVENT:
                args.update({
                    "type": "polyphonic_key_pressure",
                    "key": stream._next_byte(),
                    "pressure": stream._next_byte(),
                })
            elif event_type == CONTROLLER_CHANGE_EVENT:
                args.update({
                    "type": "controller_change",
                    "controller": stream._next_byte(),
                    "value": stream._next_byte(),
                })
            elif event_type == PROGRAM_CHANGE_EVENT:
                args.update({
                    "type": "program_change",
                    "program": stream._next_byte(),
                })
            elif event_type == CHANNEL_KEY_PRESSURE_EVENT:
                args.update({
                    "type": "channel_key_pressure",
                    "pressure": stream._next_byte(),
                })
            elif event_type == PITCH_BEND_EVENT:
                args.update({
                    "type": "pitch_bend",
                    "value": (stream._next_byte() + stream._next_byte() * 0x80) - 0x2000,  # 0 is center
                })
            else:
                raise Exception("Unsupported MIDI event code: 0x{:X}".format(event_type))
        return MidiEvent(**args)
