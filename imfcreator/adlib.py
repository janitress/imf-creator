OPL_CHANNELS = 9

# OPERATORS
MODULATORS = [0, 1, 2, 8, 9, 10, 16, 17, 18]
CARRIERS = [m + 3 for m in MODULATORS]

# REGISTERS
TEST_MSG = 0x1                  # Chip-wide
TIMER_1_COUNT_MSG = 0x2         # Chip-wide
TIMER_2_COUNT_MSG = 0x3         # Chip-wide
IRQ_RESET_MSG = 0x4             # Chip-wide
COMP_SINE_WAVE_MODE_MSG = 0x8   # Chip-wide
VIBRATO_MSG = 0x20              # Operator-based
VOLUME_MSG = 0x40               # Operator-based
ATTACK_DECAY_MSG = 0x60         # Operator-based
SUSTAIN_RELEASE_MSG = 0x80      # Operator-based
FREQ_MSG = 0xa0                 # Channel-based
BLOCK_MSG = 0xb0                # Channel-based
DRUM_MSG = 0xbd                 # Percussion mode: Tremolo / Vibrato / Percussion Mode / BD/SD/TT/CY/HH On
FEEDBACK_MSG = 0xc0             # Channel-based
WAVEFORM_SELECT_MSG = 0xe0      # # Operator-based

# BLOCK_MSG Bit Masks
KEY_OFF_MASK = 0x0  # 0000 0000
KEY_ON_MASK = 0x20  # 0010 0000
# BLOCK_MASK = 0x1c   # 0001 1100, >> 2 to get the block number
# FREQ_MSB_MASK = 0x3 # 0000 0011

BLOCK_FREQ_NOTE_MAP = [  # f-num = freq * 2^(20 - block) / 49716
    # (0, 172), (0, 183), (0, 194), (0, 205), (0, 217), (0, 230),
    # (0, 244), (0, 258), (0, 274), (0, 290), (0, 307), (0, 326),
    # MUSPLAY and the HERETIC source start with these values. Otherwise, the music sounds an octave lower.
    (0, 345), (0, 365), (0, 387), (0, 410), (0, 435), (0, 460),
    (0, 488), (0, 517), (0, 547), (0, 580), (0, 615), (0, 651),
    (0, 690), (0, 731), (0, 774), (0, 820), (0, 869), (0, 921),
    (0, 975), (1, 517), (1, 547), (1, 580), (1, 615), (1, 651),
    (1, 690), (1, 731), (1, 774), (1, 820), (1, 869), (1, 921),
    (1, 975), (2, 517), (2, 547), (2, 580), (2, 615), (2, 651),
    (2, 690), (2, 731), (2, 774), (2, 820), (2, 869), (2, 921),
    (2, 975), (3, 517), (3, 547), (3, 580), (3, 615), (3, 651),
    (3, 690), (3, 731), (3, 774), (3, 820), (3, 869), (3, 921),
    (3, 975), (4, 517), (4, 547), (4, 580), (4, 615), (4, 651),
    (4, 690), (4, 731), (4, 774), (4, 820), (4, 869), (4, 921),
    (4, 975), (5, 517), (5, 547), (5, 580), (5, 615), (5, 651),
    (5, 690), (5, 731), (5, 774), (5, 820), (5, 869), (5, 921),
    (5, 975), (6, 517), (6, 547), (6, 580), (6, 615), (6, 651),
    (6, 690), (6, 731), (6, 774), (6, 820), (6, 869), (6, 921),
    (6, 975), (7, 517), (7, 547), (7, 580), (7, 615), (7, 651),
    (7, 690), (7, 731), (7, 774), (7, 820), (7, 869), (7, 921),
    (7, 975)
    # , (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023),
    # (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023)
]

# PERCUSSION MODE
PERCUSSION_MODE_BASS_DRUM_MODULATOR = 12
PERCUSSION_MODE_BASS_DRUM_CARRIER = 15
PERCUSSION_MODE_SNARE_DRUM = 16
PERCUSSION_MODE_TOM_TOM = 14
PERCUSSION_MODE_CYMBAL = 17
PERCUSSION_MODE_HI_HAT = 13

PERCUSSION_MODE_TREMOLO_MASK = 0b10000000
PERCUSSION_MODE_VIBRATO_MASK = 0b01000000
PERCUSSION_MODE_PERCUSSION_MODE_MASK = 0b00100000
PERCUSSION_MODE_BASS_DRUM_MASK = 0b00010000
PERCUSSION_MODE_SNARE_DRUM_MASK = 0b00001000
PERCUSSION_MODE_TOM_TOM_MASK = 0b00000100
PERCUSSION_MODE_CYMBAL_MASK = 0b00000010
PERCUSSION_MODE_HI_HAT_MASK = 0b00000001


class AdlibInstrument(object):
    """Represents an adlib instrument.

    Instruments can contain one or more voices, each consisting of a modulator and a carrier.
    This largely reflects the information stored per instrument in an OP2 file.
    """
    def __init__(self, name=None, num_voices=1):
        self.name = name
        """The name of the instrument, if one is available."""
        self.use_given_note = False
        """When true, this instrument acts like a percussion instrument using given_note."""
        self.use_secondary_voice = False
        """When true, the second voice can be used in addition to the first. 
        Also, fine_tuning should be taken into account.
        """
        # Fine tune value is an index offset of frequencies table. 128 is a center, i.e. don't detune.
        # Formula of index offset is: (fine_tune / 2) - 64.
        # Each unit of fine tune field is approximately equal to 1/0.015625 of tone.
        self.fine_tuning = 0x80  # 8-bit, 0x80 = center
        self.given_note = 0  # 8-bit, for percussion
        self.num_voices = num_voices
        # Voice settings.
        self.modulator = [AdlibOperator() for _ in range(num_voices)]
        self.carrier = [AdlibOperator() for _ in range(num_voices)]
        self.feedback = [0] * num_voices  # 8-bit
        self.note_offset = [0] * num_voices  # 16-bit, signed

    def __repr__(self):
        return str(self.__dict__)

    def get_regs(self, channel, voice=0):
        mod_op = MODULATORS[channel]
        car_op = CARRIERS[channel]
        return [
            (VIBRATO_MSG | mod_op, self.modulator[voice].tvskm),
            (VOLUME_MSG | mod_op, self.modulator[voice].ksl_output),
            (ATTACK_DECAY_MSG | mod_op, self.modulator[voice].attack_decay),
            (SUSTAIN_RELEASE_MSG | mod_op, self.modulator[voice].sustain_release),
            (WAVEFORM_SELECT_MSG | mod_op, self.modulator[voice].waveform_select),
            (VIBRATO_MSG | car_op, self.carrier[voice].tvskm),
            (VOLUME_MSG | car_op, self.carrier[voice].ksl_output),
            (ATTACK_DECAY_MSG | car_op, self.carrier[voice].attack_decay),
            (SUSTAIN_RELEASE_MSG | car_op, self.carrier[voice].sustain_release),
            (WAVEFORM_SELECT_MSG | car_op, self.carrier[voice].waveform_select),
            (FEEDBACK_MSG | channel, self.feedback[voice]),  # | 0x30),
        ]

    def registers_match(self, other):
        if self.num_voices != other.num_voices:
            return False
        for v in range(self.num_voices):
            if self.modulator[v] != other.modulator[v]:
                return False
            if self.carrier[v] != other.carrier[v]:
                return False
            if self.feedback[v] != other.feedback[v]:
                return False
        return True


class AdlibOperator(object):  # MUST inherit from object for properties to work.
    """Represents an adlib operator's register values."""
    def __init__(self, tvskm=0, ksl_output=0, attack_decay=0, sustain_release=0, waveform_select=0):
        self.tvskm = 0  # tvskffff = tremolo, vibrato, sustain, ksr, frequency multiplier
        self.ksl_output = 0  # kkoooooo = key scale level, output level
        self.attack_decay = 0  # aaaadddd = attack rate, decay rate
        self.sustain_release = 0  # ssssrrrr = sustain level, release rate
        self.waveform_select = 0  # -----www = waveform select
        self.set_regs(tvskm, ksl_output, attack_decay, sustain_release, waveform_select)
        # Bit-level properties.
        AdlibOperator.tremolo = _create_bit_property("tvskm", 1, 7)
        AdlibOperator.vibrato = _create_bit_property("tvskm", 1, 6)
        AdlibOperator.sustain = _create_bit_property("tvskm", 1, 5)
        AdlibOperator.ksr = _create_bit_property("tvskm", 1, 4)
        AdlibOperator.freq_mult = _create_bit_property("tvskm", 4, 0)
        AdlibOperator.key_scale_level = _create_bit_property("ksl_output", 2, 6)
        AdlibOperator.output_level = _create_bit_property("ksl_output", 6, 0)
        AdlibOperator.attack_rate = _create_bit_property("attack_decay", 4, 4)
        AdlibOperator.decay_rate = _create_bit_property("attack_decay", 4, 0)
        AdlibOperator.sustain_level = _create_bit_property("sustain_release", 4, 4)
        AdlibOperator.release_rate = _create_bit_property("sustain_release", 4, 0)

    def set_regs(self, tvskm, ksl_output, attack_decay, sustain_release, waveform_select):
        """Sets all operator registers."""
        self.tvskm = tvskm
        self.ksl_output = ksl_output
        self.attack_decay = attack_decay
        self.sustain_release = sustain_release
        self.waveform_select = waveform_select

    def __repr__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


def _create_bit_property(var_name, bits, shift):
    """Creates a property that is a bit-wise representation of a register.

    The property performs bitshifting and value range checks.
    """
    max_value = 2 ** bits - 1
    return property(
        fget=lambda self: (getattr(self, var_name) >> shift) & max_value,
        fset=lambda self, value: setattr(self, var_name,
                                         (getattr(self, var_name) & ~(max_value << shift))
                                         | (_check_range(value, max_value) << shift))
    )


def _check_range(value, max_value):
    """Checks a value to verify that it is between 0 and maxvalue, inclusive."""
    if value is None:
        raise ValueError("Value is required.")
    if 0 <= value <= max_value:
        return value
    else:
        raise ValueError("Value should be between 0 and {} inclusive. Got: {}.".format(max_value, value))
