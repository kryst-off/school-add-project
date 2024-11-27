class PacketWrapper:
    def __init__(self, packet):
        self.packet = packet
        self.origin_pts = packet.pts
        self.origin_dts = packet.dts
