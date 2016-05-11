local function pcap2http_menu()
	local function dialog_func(python, script, pcap, browser, packet)
		local cmd = ""..python.." "..script.." --browser "..browser.." --packet "..packet.." "..pcap.."";
		os.execute(cmd);
	end
		
	new_dialog("Enter arguments using quotes only for paths with spaces", dialog_func,
		"Python.exe executable path",
		"pcap2http.py path",
		"Saved pcap(ng) path",
		"Browser.exe path",
		"Packet number")
end

register_menu("Pcap to http", pcap2http_menu, MENU_TOOLS_UNSORTED)