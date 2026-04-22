import framebuf

SET_CONTRAST        = 0x81
SET_NORM_INV        = 0xa6
SET_DISP            = 0xae
SET_SCAN_DIR        = 0xc0
SET_SEG_REMAP       = 0xa0
LOW_COLUMN_ADDRESS  = 0x00
HIGH_COLUMN_ADDRESS = 0x10
SET_PAGE_ADDRESS    = 0xB0

class SH1106(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP | 0x00,  # off
            SET_NORM_INV | 0x00,
            SET_SEG_REMAP | 0x01,
            SET_SCAN_DIR | 0x08,
            SET_CONTRAST, 0x7f,
            SET_DISP | 0x01): # on
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        for page in range(self.pages):
            self.write_cmd(SET_PAGE_ADDRESS | page)
            self.write_cmd(LOW_COLUMN_ADDRESS | 2)
            self.write_cmd(HIGH_COLUMN_ADDRESS | 0)
            self.write_data(self.buffer[page * self.width : (page + 1) * self.width])

class SH1106_I2C(SH1106):
    def __init__(self, width, height, i2c, res=None, addr=0x3c, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.res = res
        if res is not None:
            res.init(res.OUT, value=1)
        self.temp = bytearray(2)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        self.i2c.writeto(self.addr, b'\x40' + buf)