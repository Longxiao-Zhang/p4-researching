#include <core.p4>
#include <v1model.p4>

// headers
#include "include/headers.p4"
// custom header
struct headers_t {
    packet_out_header_t packet_out;
    packet_in_header_t packet_in;
    ethernet_t ethernet;
    ipv4_t ipv4;
    tcp_t tcp;
    udp_t udp;
}

struct local_metadata_t {
    bit<16>       l4_src_port;
    bit<16>       l4_dst_port;
    next_hop_id_t next_hop_id;
}
#include "include/defines.p4"
// parser
#include "include/parser.p4"
// actions 
#include "include/actions.p4"
// port counters, meters
#include "include/port_counters.p4"
#include "include/port_meters.p4"
// packet io
#include "include/packet_io.p4"
// checksums
#include "include/checksums.p4"
// wcmp
#include "include/wcmp.p4"
// host meter table
#include "include/host_meter_table.p4"
// table 0
#include "include/table0.p4"


//------------------------------------------------------------------------------
// INGRESS PIPELINE
//------------------------------------------------------------------------------

control ingress(inout headers_t hdr,
                inout local_metadata_t local_metadata,
                inout standard_metadata_t standard_metadata) {

    apply {
        port_counters_ingress.apply(hdr, standard_metadata);
        port_meters_ingress.apply(hdr, standard_metadata);
        packetio_ingress.apply(hdr, standard_metadata);
        table0_control.apply(hdr, local_metadata, standard_metadata);
        host_meter_control.apply(hdr, local_metadata, standard_metadata);
        wcmp_control.apply(hdr, local_metadata, standard_metadata);
    }
}

//------------------------------------------------------------------------------
// EGRESS PIPELINE
//------------------------------------------------------------------------------

control egress(inout headers_t hdr,
               inout local_metadata_t local_metadata,
               inout standard_metadata_t standard_metadata) {

    apply {
        port_counters_egress.apply(hdr, standard_metadata);
        port_meters_egress.apply(hdr, standard_metadata);
        packetio_egress.apply(hdr, standard_metadata);
    }
}

//------------------------------------------------------------------------------
// SWITCH INSTANTIATION
//------------------------------------------------------------------------------

V1Switch(
    parser_impl(),
    verify_checksum_control(),
    ingress(),
    egress(),
    compute_checksum_control(),
    deparser()
) main;