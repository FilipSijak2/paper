#pragma once
#include <stdint.h>

// Packet layout (little endian)
// uint32_t header = 0xA55AA55A
// float linear_mps
// float angular_rps
// uint16_t crc16 (computed over header+linear+angular fields)
// uint16_t tail = 0x55AA
// Total 16 bytes

static const uint32_t CMD_HEADER = 0xA55AA55A;
static const uint16_t CMD_TAIL   = 0x55AA;

struct __attribute__((packed)) CommandPacket {
    uint32_t header;
    float linear;
    float angular;
    uint16_t crc;
    uint16_t tail;
};

inline void fill_command_packet(CommandPacket &pkt, float lin, float ang, uint16_t (*crc_fn)(const uint8_t*, uint16_t)) {
    pkt.header = CMD_HEADER;
    pkt.linear = lin;
    pkt.angular = ang;
    pkt.tail = CMD_TAIL; // set tail early for CRC range clarity
    // Compute CRC over first 12 bytes (header+linear+angular)
    pkt.crc = crc_fn(reinterpret_cast<const uint8_t*>(&pkt), 4 + 4 + 4);
}

inline bool validate_command_packet(const CommandPacket &pkt, uint16_t (*crc_fn)(const uint8_t*, uint16_t)) {
    if (pkt.header != CMD_HEADER || pkt.tail != CMD_TAIL) return false;
    uint16_t expect = crc_fn(reinterpret_cast<const uint8_t*>(&pkt), 12);
    return expect == pkt.crc;
}
