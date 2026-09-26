from ladder_harness.iolist import IoList
from ladder_harness.melsec.devices import dev


def test_load_and_safety(tmp_path):
    f = tmp_path / "io.csv"
    f.write_text("tag,device,description,signal,range,units,station,safety,notes\n"
                 "ES-0001,X0,E-stop healthy,DI,,,CELL,SAFETY,\n"
                 "XV-2003,Y21,Fill valve,DO,,,ST20,,\n")
    io = IoList.load_csv(f)
    assert io.safety_devices() == {dev("X0")}
    assert io.by_device[dev("Y21")].tag == "XV-2003"
    assert io.io_devices() == {dev("X0"), dev("Y21")}
