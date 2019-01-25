#!/usr/bin/env python
import os, sys
from Scripts import *

class CheckAudio:
    def __init__(self):
        self.r = run.Run()
        self.u = utils.Utils("CheckAudio")
        self.kextstat = None
        self.log = ""
        self.vendors = {
            "8086":"Intel",
            "10de":"Nvidia",
            "1002":"AMD",
            "10ec":"Realtek",
            "111d":"IDT"
        }

    def get_codecs(self):
        # Get our audio codec list
        ioreg = self.r.run({"args":["ioreg","-rxn","IOHDACodecDevice"]})[0].split("\n")
        # Iterate the list looking for devices
        codecs = []
        codec = None
        for x in ioreg:
            if "iohdacodecvendorid" in x.lower():
                codec = x.split(" = ")[1].lower().replace("ffffffff","")
            if codec and "iohdacodecrevisionid" in x.lower():
                codecs.append({"codec":codec,"revision":x.split(" = ")[1].lower()})
                # Clear the codec var
                codec = None
        return codecs

    def get_hdef(self):
        # Iterate looking for our HDEF device(s)
        # returns a list of devices@addr
        ioreg = self.r.run({"args":["ioreg", "-l", "-p", "IOService", "-w0"]})[0].split("\n")
        hdef = []
        for line in ioreg:
            if " HDEF@" in line:
                hdef.append(line)
        return hdef

    def get_info(self, hdef):
        # Returns a dict of the properties of the HDEF device
        # as individual text items
        # First split up the text and find the device
        try:
            hid = "HDEF@" + hdef.split("HDEF@")[1].split()[0]
        except:
            return None
        # Got our HDEF address - get the full info
        hd = self.r.run({"args":["ioreg", "-p", "IODeviceTree", "-n", hid, "-w0"]})[0]
        if not len(hd):
            return None
        primed = False
        hdevice = {"name":"Unknown", "parts":{}}
        for line in hd.split("\n"):
            if not primed and not "HDEF@" in line:
                continue
            if not primed:
                # Has HDEF
                try:
                    hdevice["name"] = "HDEF@" + line.split("HDEF@")[1].split()[0]
                except:
                    hdevice["name"] = "Unknown"
                primed = True
                continue
            # Primed, but not HDEF
            if "+-o" in line:
                # Past our prime
                primed = False
                continue
            # Primed, not HDEF, not next device - must be info
            try:
                name = line.split(" = ")[0].split('"')[1]
                hdevice["parts"][name] = line.split(" = ")[1]
            except Exception as e:
                pass
        return hdevice

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
        if not "_items" in xml[0] or not len(xml[0]["_items"]) or not "_items" in xml[0]["_items"][0]:
            return []
        audio_devices = xml[0]["_items"][0]["_items"]
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
                name = self.vendors.get(ven,"Unknown")
                self.lprint(" - {} {}".format(name, x["codec"][6:]))
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
        self.lprint("Locating AppleHDA...")
        hda_vers = self.locate("AppleHDA")
        if not hda_vers:
            self.lprint(" - Not loaded!")
        else:
            self.lprint(" - Found v{}".format(hda_vers))
        self.lprint("")
        self.lprint("Locating HDEF devices...")
        hdef_list = self.get_hdef()
        if not len(hdef_list):
            self.lprint(" - None found!")
            self.lprint("")
        else:
            self.lprint(" - Located {}".format(len(hdef_list)))
            self.lprint("")
            self.lprint("Iterating HDEF devices:")
            self.lprint("")
            for h in hdef_list:
                h_dict = self.get_info(h)
                try:
                    locs = h_dict['name'].split("@")[1].split(",")
                    loc = "PciRoot(0x0)/Pci(0x{},0x{})".format(locs[0],locs[1])
                except:
                    loc = "Unknown Location"
                self.lprint(" - {} - {}".format(h_dict["name"], loc))
                max_len = len("no-controller-patch")
                for x in ["built-in","alc-layout-id","layout-id","hda-gfx","no-controller-patch"]:
                    len_adjusted = x + ":" + " "*(max_len - len(x))
                    self.lprint(" --> {} {}".format(len_adjusted, h_dict.get("parts",{}).get(x,"Not Present")))
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
