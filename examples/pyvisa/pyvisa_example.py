import pytest


@pytest.fixture()
def signal_generator(target):
    return target.get_driver("PyVISADriver").get_session()


def test_with_signal_generator_example(signal_generator):
    signal_generator.write("*RST")

    # Setup channel 1
    signal_generator.write("C1:BSWV WVTP,SQUARE,HLEV,5,LLEV,0,DUTY,50")
    # Switch on channel 1
    signal_generator.write("C1:OUTP ON,LOAD,HZ,PLRT,NOR")
