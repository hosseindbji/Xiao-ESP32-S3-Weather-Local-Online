import time
import machine

class DHTBase:
    def __init__(self, pin):
        self.pin = machine.Pin(pin)
        self.buf = bytearray(5)

    def measure(self):
        self._send_init_signal()
        self._parse_data()

    def _send_init_signal(self):
        self.pin.init(machine.Pin.OUT)
        self.pin.value(0)
        time.sleep_ms(20)  # at least 18ms for DHT11
        self.pin.value(1)
        time.sleep_us(40)
        self.pin.init(machine.Pin.IN)

    def _parse_data(self):
        buf = self.buf
        idx = 0
        cnt = 0
        while self.pin.value() == 1:
            pass
        while self.pin.value() == 0:
            pass
        while self.pin.value() == 1:
            pass

        for i in range(40):
            while self.pin.value() == 0:
                pass
            t = time.ticks_us()
            while self.pin.value() == 1:
                pass
            if time.ticks_diff(time.ticks_us(), t) > 50:
                buf[idx >> 3] |= 1 << (7 - (idx & 7))
            else:
                buf[idx >> 3] &= ~(1 << (7 - (idx & 7)))
            idx += 1

        if ((buf[0] + buf[1] + buf[2] + buf[3]) & 0xFF) != buf[4]:
            raise Exception("Checksum error")

    def humidity(self):
        raise NotImplementedError()

    def temperature(self):
        raise NotImplementedError()


class DHT11(DHTBase):
    def humidity(self):
        return self.buf[0]

    def temperature(self):
        return self.buf[2]


class DHT22(DHTBase):
    def humidity(self):
        return ((self.buf[0] << 8) + self.buf[1]) * 0.1

    def temperature(self):
        t = ((self.buf[2] & 0x7F) << 8) + self.buf[3]
        t *= 0.1
        if self.buf[2] & 0x80:
