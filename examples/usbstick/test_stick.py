def test_stick_plugin(stick):
    stick.plug_in()


def test_stick_upload(stick):
    stick.plug_out()
    stick.upload_file('testfile')
    stick.plug_in()
