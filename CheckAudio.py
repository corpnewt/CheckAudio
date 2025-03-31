#!/usr/bin/env python
import os, sys
from Scripts import ioreg, plist, run, utils

class CheckAudio:
    def __init__(self):
        self.u = utils.Utils("CheckAudio")
        # Verify running OS
        if not sys.platform.lower() == "darwin":
            self.u.head("Wrong OS!")
            print("")
            print("This script can only be run on macOS!")
            print("")
            self.u.grab("Press [enter] to exit...")
            exit(1)
        self.r = run.Run()
        self.i = ioreg.IOReg()
        self.kextstat = None
        self.log = ""
        self.vendors = {
            "1002":"AMD",
            "1022":"AMD Zen",
            "11d4":"AnalogDevices",
            "1013":"CirrusLogic",
            "14f1":"Conexant",
            "1102":"Creative",
            "111d":"IDT",
            "8086":"Intel",
            "10de":"Nvidia",
            "10ec":"Realtek",
            "8384":"SigmaTel",
            "1106":"VIA"
        }
        self.ioreg = None

    def get_codecs(self):
        # Get our audio codec list
        ioreg = self.r.run({"args":["ioreg","-d1","-rn","IOHDACodecDevice"]})[0].split("\n")
        # Iterate the list looking for devices
        codecs = []
        codec = None
        for x in ioreg:
            if "iohdacodecvendorid" in x.lower():
                try:
                    codec = hex(int(x.split(" = ")[1]) & 0xFFFFFFFF).lower()
                except:
                    # Reset on failure
                    codec = None
            if codec and "iohdacodecrevisionid" in x.lower():
                try:
                    codecs.append({
                        "codec":codec,
                        "revision":hex(int(x.split(" = ")[1])).lower()
                    })
                finally:
                    # Clear the codec var
                    codec = None
        return codecs

    def get_inputs_outputs(self):
        # Runs system_profiler SPAudioDataType and parses data
        n_head = "        " # Sets the pad for the name header
        n_foot = ":"        # Sets the last char for the header
        devs = self.r.run({"args":["system_profiler","-xml","SPAudioDataType"]})[0]
        dev_list = []
        try:
            xml = plist.loads(devs)
        except:
            xml = []
        if not len(xml):
            return []
        audio_devices = []
        if not "_items" in xml[0] or not len(xml[0]["_items"]):
            return []
        for x in xml[0]["_items"]:
            if not "_items" in x:
                continue
            audio_devices.extend(x["_items"])
        # Walk the list
        for x in audio_devices:
            try:
                new_item = {
                    "name": x.get("_name","Unknown"),
                    "out_source": x.get("coreaudio_output_source",None),
                    "out_count": x.get("coreaudio_device_output",None),
                    "in_source": x.get("coreaudio_input_source",None),
                    "in_count": x.get("coreaudio_device_input",None),
                    "type": x.get("coreaudio_device_transport",None)
                }
                dev_list.append(new_item)
            except:
                continue
        return dev_list

    def get_kextstat(self, force = False):
        # Gets the kextstat list if needed
        if not self.kextstat or force:
            self.kextstat = self.r.run({"args":"kextstat"})[0]
        return self.kextstat

    def get_boot_args(self):
        # Attempts to pull the boot-args from nvram
        out = self.r.run({"args":["nvram","-p"]})
        for l in out[0].split("\n"):
            if "boot-args" in l:
                return "\t".join(l.split("\t")[1:])
        return None

    def get_os_version(self):
        # Scrape sw_vers
        prod_name  = self.r.run({"args":["sw_vers","-productName"]})[0].strip()
        prod_vers  = self.r.run({"args":["sw_vers","-productVersion"]})[0].strip()
        build_vers = self.r.run({"args":["sw_vers","-buildVersion"]})[0].strip()
        if build_vers: build_vers = "({})".format(build_vers)
        return " ".join([x for x in (prod_name,prod_vers,build_vers) if x])

    def locate(self, kext):
        # Gathers the kextstat list - then parses for loaded kexts
        ks = self.get_kextstat()
        # Verifies that our name ends with a space
        if not kext[-1] == " ":
            kext += " "
        for x in ks.split("\n")[1:]:
            if kext.lower() in x.lower():
                # We got the kext - return the version
                try:
                    v = x.split("(")[1].split(")")[0]
                except:
                    return "?.?"
                return v
        return None

    def lprint(self, message):
        print(message)
        self.log += message + "\n"

    def main(self):
        self.u.head()
        self.lprint("")
        self.lprint("Finding Codecs...")
        codecs = self.get_codecs()
        if not len(codecs):
            self.lprint(" - None found!")
        else:
            self.lprint(" - Found {}".format(len(codecs)))
            self.lprint("")
            self.lprint("Iterating codecs:")
            self.lprint("")
            for x in codecs:
                # Resolve the manufacturer name
                ven = x["codec"][2:6]
                name = self.vendors.get(ven.lower(),x["codec"][:6])
                self.lprint(" - {} 0x{}".format(name, x["codec"][6:]))
                self.lprint(" --> ID:       {}".format(x["codec"]))
                self.lprint(" --> Revision: {}".format(x["revision"]))
                self.lprint("")
        self.lprint("Checking kexts:")
        self.lprint("")
        self.lprint("Locating Lilu...")
        lilu_vers = self.locate("Lilu")
        if not lilu_vers:
            self.lprint(" - Not loaded! AppleALC and WhateverGreen need this!")
        else:
            self.lprint(" - Found v{}".format(lilu_vers))
            self.lprint("Checking for Lilu plugins...")
            self.lprint(" - Locating AppleALC...")
            alc_vers = self.locate("AppleALC")
            if not alc_vers:
                self.lprint(" --> Not loaded! Onboard and HDMI/DP audio may not work!")
            else:
                self.lprint(" --> Found v{}".format(alc_vers))
            self.lprint(" - Locating WhateverGreen...")
            weg_vers = self.locate("WhateverGreen")
            if not weg_vers:
                self.lprint(" --> Not loaded! HDMI/DP audio may not work!")
            else:
                self.lprint(" --> Found v{}".format(weg_vers))
        self.lprint("Locating AppleHDAController...")
        hda_c_vers = self.locate("AppleHDAController")
        if not hda_c_vers:
            self.lprint(" - Not loaded!")
        else:
            self.lprint(" - Found v{}".format(hda_c_vers))
        self.lprint("Locating AppleHDA...")
        hda_vers = self.locate("AppleHDA")
        if not hda_vers:
            self.lprint(" - Not loaded!")
        else:
            self.lprint(" - Found v{}".format(hda_vers))
        self.lprint("")
        os_vers = self.get_os_version()
        self.lprint("Current OS Version: {}".format(os_vers or "Unknown!"))
        self.lprint("")
        boot_args = self.get_boot_args()
        self.lprint("Current boot-args: {}".format(boot_args or "None set!"))
        self.lprint("")
        all_devs = self.i.get_all_devices()
        for dev in ["HDEF","HDAU"]:
            self.lprint("Locating {} devices...".format(dev))
            hdef_list = [x for x in all_devs.values() if x.get("name_no_addr") == dev]
            if not len(hdef_list):
                self.lprint(" - None found!")
                self.lprint("")
            else:
                self.lprint(" - Located {}".format(len(hdef_list)))
                self.lprint("")
                self.lprint("Iterating {} devices:".format(dev))
                self.lprint("")
                for h in hdef_list:
                    h_dict = h.get("info",{})
                    loc = h.get("device_path")
                    self.lprint(" - {} - {}".format(h["name"], loc or "Could Not Resolve Device Path"))
                    max_len = len("no-controller-patch:")
                    name = self.i.get_pci_device_name(h_dict,use_unknown=False)
                    if name:
                        self.lprint(" --> {} {}".format("name:".ljust(max_len),name))
                    for x in ["built-in","alc-layout-id","layout-id","hda-gfx","no-controller-patch","acpi-path"]:
                        val = h_dict.get(x,"Not Present")
                        if val[0]=="<" and val[-1]==">" and val[1]!='"' and val[-1]!='"':
                            # Got some likely little endian hex data - try to get a number
                            try:
                                val_hex = list("0"*(len(val[1:-1])%2)+val[1:-1])
                                val_rev = "".join(["".join(val_hex[i:i+2]) for i in range(0,len(val_hex),2)][::-1])
                                val = "{} ({})".format(val,int(val_rev,16))
                            except Exception:
                                pass
                        self.lprint(" --> {} {}".format((x+":").ljust(max_len), val))
                    self.lprint("")
        # Show all available outputs
        self.lprint("Gathering inputs/outputs...")
        outs = self.get_inputs_outputs()
        if not len(outs):
            self.lprint(" - None found!")
            self.lprint("")
        else:
            self.lprint(" - Located {}".format(len(outs)))
            self.lprint("")
            self.lprint("Iterating Inputs and Outputs:")
            self.lprint("")
            for out in outs:
                self.lprint(" - {}".format(out["name"]))
                if out["type"]:
                    self.lprint(" --> Type:            {}".format(out["type"].split("_")[-1].capitalize()))
                if out["in_count"]:
                    self.lprint(" --> Inputs:          {}".format(out["in_count"]))
                    self.lprint(" ----> Input Source:  {}".format(out["in_source"]))
                if out["out_count"]:
                    self.lprint(" --> Outputs:         {}".format(out["out_count"]))
                    self.lprint(" ----> Output Source: {}".format(out["out_source"]))
                self.lprint("")
        print("Saving log...")
        print("")
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        with open("Audio.log","w") as f:
            f.write(self.log)
        print("Done.")
        print("")
        

if __name__ == '__main__':
    # os.chdir(os.path.dirname(os.path.realpath(__file__)))
    a = CheckAudio()
    a.main()
