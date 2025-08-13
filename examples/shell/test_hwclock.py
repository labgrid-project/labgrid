from datetime import datetime


def test_hwclock_rate(command):
    """Test that the hardware clock rate is not too inaccurate."""
    result = command.run_check("hwclock -c | head -n 3")
    hw_time, sys_time, freq_offset_ppm, tick = result[-1].strip().split()
    assert abs(int(freq_offset_ppm)) < 1000


def test_hwclock_value(command):
    """Test that the hardware clock has the correct time.

    If the time is wrong, it is set once and tested again.
    """

    def get_time():
        result = command.run_check("hwclock --utc --show")[0].strip()
        return datetime.strptime(result, "%Y-%m-%d %H:%M:%S.%f+0:00")

    def set_time(time):
        time = time.strftime("%Y-%m-%d %H:%M:%S.%f+0:00")
        command.run_check(f'hwclock --utc --set --date "{time}"')

    offset = abs((get_time() - datetime.utcnow()).total_seconds())
    if offset > 60:
        set_time(datetime.utcnow())
        offset = abs((get_time() - datetime.utcnow()).total_seconds())
    assert offset < 60
