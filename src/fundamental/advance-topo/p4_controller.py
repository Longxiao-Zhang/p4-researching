#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import argparse, grpc, os, sys
from time import sleep

# set our lib path
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
        '../../../utils/'))
# And then we import
import p4runtime_lib.bmv2
from p4runtime_lib.switch import ShutdownAllSwitchConnections
import p4runtime_lib.helper

def setDefaultDrop(p4info_helper,ingress_sw):
    """
        設定 drop
    """
    table_entry = p4info_helper.buildTableEntry(
        table_name="Basic_ingress.ipv4_lpm",
        default_action=True,
        action_name="Basic_ingress.drop",
        action_params={})
    ingress_sw.WriteTableEntry(table_entry)
    print "Installed Default Drop Rule on %s" % ingress_sw.name

def writeForwardRules(p4info_helper,ingress_sw,
    dst_eth_addr,port,dst_ip_addr):
    """
        Install rules:

        做到原本 sx-runtime.json 的工作
            p4info_helper:  the P4Info helper
            ingress_sw:     the ingress switch connection
            dst_eth_addr:   the destination IP to match in the ingress rule
            port:           port of switch
            dst_ip_addr:    the destination Ethernet address to write in the egress rule
    """

    # 1. Ingress rule
    table_entry = p4info_helper.buildTableEntry(
        table_name="Basic_ingress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr,32)
        },
        action_name="Basic_ingress.ipv4_forward",
        action_params={
            "dstAddr": dst_eth_addr,
            "port": port
        })
    # write into ingress of target sw
    ingress_sw.WriteTableEntry(table_entry)
    print "Installed ingress forward rule on %s" % ingress_sw.name

def modifyForwardRules(p4info_helper, ingress_sw,
    dst_eth_addr, port, dst_ip_addr):
    """
        Modify Rules
    """
    table_entry = p4info_helper.buildTableEntry(
        table_name="Basic_ingress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, 32)
        },
        action_name="Basic_ingress.ipv4_forward",
        action_params={
            "dstAddr": dst_eth_addr,
            "port": port
        })
    ingress_sw.ModifyTableEntry(table_entry)
    print "Modified ingress forward rule on %s" % ingress_sw.name

def deleteForwardRules(p4info_helper, ingress_sw,
    dst_eth_addr, port, dst_ip_addr):
    """
        Delete Rules
    """
    table_entry = p4info_helper.buildTableEntry(
        table_name="Basic_ingress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, 32)
        },
        action_name="Basic_ingress.ipv4_forward",
        action_params={
            "dstAddr": dst_eth_addr,
            "port": port
        })
    ingress_sw.DeleteTableEntry(table_entry)
    print "Deleted ingress forward rule on %s" % ingress_sw.name

def clearAllRules(p4info_helper, sw):
    print '\n----- Clear all table rules for %s -----' % sw.name
    # fetch all response
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            # delete this entry
            sw.DeleteTableEntry(entry)
            print "Delete ingress forward rule on %s" % sw.name

def readTableRules(p4info_helper, sw):
    """
        Reads the table entries from all tables on the switch.
        Args:
            p4info_helper:  the P4Info helper
            sw:             the switch connection
    """
    print '\n----- Reading table rules for %s ------' % sw.name
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            # TOOD:
            # use the p4info_helper to translate the IDs in the entry to names
            table_name = p4info_helper.get_tables_name(entry.table_id)
            print '%s: ' % table_name,
            for m in entry.match:
                print p4info_helper.get_match_field_name(table_name, m.field_id)
                print '%r' % (p4info_helper.get_match_field_value(m),),
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print '->', action_name,
            for p in action.params:
                print p4info_helper.get_action_param_name(action_name, p.param_id),
                print '%r' % p.value
            print

def printCounter(p4info_helper, sw, counter_name, index):
    """
        讀取指定的 counter 於指定 switch 上的 index
        於這支範例程式中，index 是利用 tunnel ID 來標記
        若 index 為 0，當將會 return 所有該 counter 的 values
        Args:
            p4info_helper:  the P4Info Helper
            sw:             the switch connection
            counter_name:   the name of the counter from the P4 program
            index:          the counter index (in our case, the Tunnel ID)
    """
    for response in sw.ReadCounters(p4info_helper.get_counters_id(counter_name), index):
        for entity in response.entities:
            counter = entity.counter_entry
            print "[SW: %s][Cnt: %s][Port: %d]: %d packets (%d bytes)" % (sw.name,counter_name, index,counter.data.packet_count, counter.data.byte_count)
            return counter.data.packet_count

def printGrpcError(e):
    print "gRPC Error: ", e.details(),
    status_code = e.code()
    print "(%s)" % status_code.name,
    # detail about sys.exc_info - https://docs.python.org/2/library/sys.html#sys.exc_info
    traceback = sys.exc_info()[2]
    print "[%s:%s]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno)

def debug(p4info_helper,s1,s2,s3,s4,s5):
    # 並於每 2 秒內打印 tunnel counters
        flag = 0
        while True:
            sleep(2)
            print '\n============ Reading Packet counters on each switch =============='
            # 最後一個參數為 tunnel ID ! (e.g. Index)
            # 這個範例中用 egress port number 作為 index
            # 監控該 device 上所有對外出口累積的使用量
            # s1
            printCounter(p4info_helper, s1, "Basic_ingress.PktCounter", 0)
            # s2
            pkt_s2 = printCounter(p4info_helper, s2, "Basic_ingress.PktCounter", 0)
            if pkt_s2 > 50 and flag == 0 :
                # then we can modify forwarding rule
                modifyForwardRules(p4info_helper,ingress_sw=s1,
                        dst_eth_addr="00:00:00:05:04:00",port=5,dst_ip_addr="10.0.5.4")
                modifyForwardRules(p4info_helper,ingress_sw=s5,
                        dst_eth_addr="00:00:05:04:00:00",port=5,dst_ip_addr="10.0.1.1")
                # write new rules
                writeForwardRules(p4info_helper,ingress_sw=s3,
                        dst_eth_addr="00:00:00:05:04:00",port=2,dst_ip_addr="10.0.5.4")
                writeForwardRules(p4info_helper,ingress_sw=s3,
                        dst_eth_addr="00:00:05:04:00:00",port=1,dst_ip_addr="10.0.1.1")
                # debug - test delete
                """
                    clearAllRules(p4info_helper,s1)
                    clearAllRules(p4info_helper,s2)
                    clearAllRules(p4info_helper,s3)
                    clearAllRules(p4info_helper,s4)
                    clearAllRules(p4info_helper,s5)
                """
                flag=1
            # s3
            pkt_s3 = printCounter(p4info_helper, s3, "Basic_ingress.PktCounter", 0)
            # s4
            pkt_s4 = printCounter(p4info_helper, s4, "Basic_ingress.PktCounter", 0)
            # s5
            printCounter(p4info_helper, s5, "Basic_ingress.PktCounter", 0)

def main(p4info_file_path, bmv2_file_path, mode):
    # Instantiate a P4Runtime helper from the p4info file
    # - then need to read from the file compile from P4 Program, which call .p4info
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        """
            建立與範例當中使用到的兩個 switch - s1, s2
            使用的是 P4Runtime gRPC 的連線。
            並且 dump 所有的 P4Runtime 訊息，並送到 switch 上以 txt 格式做儲存
            - 以這邊 P4 的封裝來說， port no 起始從 50051 開始
         """
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')
        # for s3
        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name="s3",
            address='127.0.0.1:50053',
            device_id=2,
            proto_dump_file='logs/s3-p4runtime-requests.txt')

        s4 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name="s4",
            address='127.0.0.1:50054',
            device_id=3,
            proto_dump_file='logs/s4-p4runtime-requests.txt')

        s5 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name="s5",
            address='127.0.0.1:50055',
            device_id=4,
            proto_dump_file='logs/s5-p4runtime-requests.txt')

        # 傳送 master arbitration update message 來建立，使得這個 controller 成為
        # master (required by P4Runtime before performing any other write operation)
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()
        s4.MasterArbitrationUpdate()
        s5.MasterArbitrationUpdate()

        # 安裝目標 P4 程式到 switch 上
        s1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                        bmv2_json_file_path=bmv2_file_path)
        print "Installed P4 Program using SetForardingPipelineConfig on s1"

        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                        bmv2_json_file_path=bmv2_file_path)
        print "Installed P4 Program using SetForardingPipelineConfig on s2"

        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                        bmv2_json_file_path=bmv2_file_path)
        print "Installed P4 Program using SetForardingPipelineConfig on s3"

        s4.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                        bmv2_json_file_path=bmv2_file_path)
        print "Installed P4 Program using SetForardingPipelineConfig on s4"

        s5.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                        bmv2_json_file_path=bmv2_file_path)
        print "Installed P4 Program using SetForardingPipelineConfig on s5"

        # 設定 default action
        #setDefaultDrop(p4info_helper,ingress_sw=s1)
        #setDefaultDrop(p4info_helper,ingress_sw=s2)
        #setDefaultDrop(p4info_helper,ingress_sw=s3)
        #setDefaultDrop(p4info_helper,ingress_sw=s4)
        #setDefaultDrop(p4info_helper,ingress_sw=s5)

        # 設定 forward rules
        # - s1, host-links
        writeForwardRules(p4info_helper,ingress_sw=s1,
                        dst_eth_addr="00:00:00:00:01:01",port=1,dst_ip_addr="10.0.1.1")
        writeForwardRules(p4info_helper,ingress_sw=s1,
                        dst_eth_addr="00:00:00:00:01:02",port=2,dst_ip_addr="10.0.1.2")
        writeForwardRules(p4info_helper,ingress_sw=s1,
                        dst_eth_addr="00:00:00:00:01:03",port=3,dst_ip_addr="10.0.1.3")
        writeForwardRules(p4info_helper,ingress_sw=s1,
                        dst_eth_addr="00:00:00:05:04:00",port=4,dst_ip_addr="10.0.5.4")
        writeForwardRules(p4info_helper,ingress_sw=s1,
                        dst_eth_addr="00:00:00:05:05:00",port=5,dst_ip_addr="10.0.5.5")
        writeForwardRules(p4info_helper,ingress_sw=s1,
                        dst_eth_addr="00:00:00:05:06:00",port=6,dst_ip_addr="10.0.5.6")
        # - s2
        writeForwardRules(p4info_helper,ingress_sw=s2,
                        dst_eth_addr="00:00:00:05:04:00",port=1,dst_ip_addr="10.0.1.1")
        writeForwardRules(p4info_helper,ingress_sw=s2,
                        dst_eth_addr="00:00:05:04:00:00",port=2,dst_ip_addr="10.0.5.4")
        # - s3
        writeForwardRules(p4info_helper,ingress_sw=s3,
                        dst_eth_addr="00:00:00:05:05:00",port=1,dst_ip_addr="10.0.1.2")
        writeForwardRules(p4info_helper,ingress_sw=s3,
                        dst_eth_addr="00:00:05:05:00:00",port=2,dst_ip_addr="10.0.5.5")
        # - s4
        writeForwardRules(p4info_helper,ingress_sw=s4,
                        dst_eth_addr="00:00:00:05:06:00",port=1,dst_ip_addr="10.0.1.3")
        writeForwardRules(p4info_helper,ingress_sw=s4,
                        dst_eth_addr="00:00:05:06:00:00",port=2,dst_ip_addr="10.0.5.6")
        # - s5
        writeForwardRules(p4info_helper,ingress_sw=s5,
                        dst_eth_addr="00:00:00:00:05:04",port=1,dst_ip_addr="10.0.5.4")
        writeForwardRules(p4info_helper,ingress_sw=s5,
                        dst_eth_addr="00:00:00:00:05:05",port=2,dst_ip_addr="10.0.5.5")
        writeForwardRules(p4info_helper,ingress_sw=s5,
                        dst_eth_addr="00:00:00:00:05:06",port=3,dst_ip_addr="10.0.5.6")
        writeForwardRules(p4info_helper,ingress_sw=s5,
                        dst_eth_addr="00:00:05:04:00:00",port=4,dst_ip_addr="10.0.1.1")
        writeForwardRules(p4info_helper,ingress_sw=s5,
                        dst_eth_addr="00:00:05:05:00:00",port=5,dst_ip_addr="10.0.1.2")
        writeForwardRules(p4info_helper,ingress_sw=s5,
                        dst_eth_addr="00:00:05:06:00:00",port=6,dst_ip_addr="10.0.1.3")

        # 完成寫入後，我們來讀取 s1~s5 的 table entries
        readTableRules(p4info_helper, s1)
        readTableRules(p4info_helper, s2)
        readTableRules(p4info_helper, s3)
        readTableRules(p4info_helper, s4)
        readTableRules(p4info_helper, s5)

        if mode is "advance":
            debug(p4info_helper,s1,s2,s3,s4,s5)

    except KeyboardInterrupt:
        # using ctrl + c to exit
        print "Shutting down."
    except grpc.RpcError as e:
        printGrpcError(e)

    # Then close all the connections
    ShutdownAllSwitchConnections()


if __name__ == '__main__':
    """ Simple P4 Controller
        Args:
            p4info:     指定 P4 Program 編譯產生的 p4info (PI 制定之格式、給予 controller 讀取)
            bmv2-json:  指定 P4 Program 編譯產生的 json 格式，依據 backend 不同，而有不同的檔案格式
     """

    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    # Specified result which compile from P4 program
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
            type=str, action="store", required=False,
            default="./advance.p4info")
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
            type=str, action="store", required=False,
            default="./advance.json")
    parser.add_argument('--mode', help='Specify the mode of controller.',
            type=str, action="store", required=False,
            default="advance")
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print "\np4info file not found: %s\nPlease compile the target P4 program first." % args.p4info
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print "\nBMv2 JSON file not found: %s\nPlease compile the target P4 program first." % args.bmv2_json
        parser.exit(1)

    # Pass argument into main function
    main(args.p4info, args.bmv2_json, args.mode)
