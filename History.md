<!-- HISTORY -->
## History

* 0.37.0 - 09.12.2025
  * Open Windows function rearrangement.
* 0.36.0 - 09.12.2025
  * Added MS Orca MSI editor installer (Windows).
* 0.35.1 - 09.12.2025
  * Automating ESET Internet Security uninstall.
* 0.35.0 - 08.12.2025
  * Added ESET Internet Security installer (Windows).
  * Changed base installer class and all the subclass to auto name and dir_path.
* 0.34.0 - 08.12.2025
  * Added RDP GPU support enabler (Windows).
* 0.33.0 - 08.12.2025
  * Added autocompletion in 'available' method.
* 0.32.0 - 08.12.2025
  * Added runas admin on windows.
* 0.31.0 - 08.12.2025
  * Fixed dependencies upgrade issue.
* 0.30.1 - 08.12.2025
  * Fixed auto-complete issue for aliases in interactive.
* 0.30.0 - 08.12.2025
  * Fixed chocolatey and winget wrappers. 
* 0.29.1 - 06.12.2025
  * Fixed robocorp installer.
* 0.29.0 - 04.12.2025
  * Added shorter method aliases.
* 0.28.0 - 04.12.2025
  * Added main version output.
* 0.27.0 - 04.12.2025
  * Added interactive console mode with autocomplete.
* 0.26.0 - 04.12.2025
  * Each dependency now has its own 'is_installed()' method.
* 0.25.0 - 04.12.2025
  * Added Notepad++ installer (Windows).
* 0.24.0 - 04.12.2025
  * Added qBittorrent installer (Windows).
* 0.23.2 - 03.12.2025
  * Fixed Chocolatey installer.
  * Added Winget fallback to Chocolatey wrapper.
* 0.23.1 - 03.12.2025
  * Fixed dependency installation for the 'upgrade' methods.
* 0.23.0 - 03.12.2025
  * Fixed aggregated error output in powershell wrapper.
  * Fixed missing parts in winget installation.
  * Added choco wrapper.
  * Some winget wrapper improvements.
  * Total Commander moved to Chocolatey installer.
* 0.22.1 - 27.11.2025
  * Winget installer added availability enforcement.
* 0.22.0 - 27.11.2025
  * Added dependencies check for the 'upgrade' method.
* 0.21.0 - 27.11.2025
  * Added admin requirement check for specific methods.
* 0.20.1-2 - 27.11.2025
  * Fix in Chocolatey installer (Windows).
* 0.20.0 - 27.11.2025
  * Added Chocolatey installer (Windows).
  * Changed core method 'update' to 'upgrade'.
* 0.19.0 - 24.11.2025
  * Added Total Commander installer (Windows).
* 0.18.0 - 24.11.2025
  * Added pbtk python script installer (Windows + Debian).
* 0.17.0 - 24.11.2025
  * Split VS Build Tools installer from Tesseract OCR Manager (Windows).
* 0.16.0 - 13.11.2025
  * Added FFMPEG installer (Windows).
  * Added WinGet installer/Repair (Windows).
  * Modules folder moved upper on hierarchy.
  * Added more helpers.
  * Minor fixes.
* 0.15.0 - 30.10.2025
  * Added Docker installer (Debian).
  * Minor fixes.
* 0.14.0 - 26.10.2025
  * Added qTorrent installer (Debian).
  * Tesseract OCR installer help fix (Windows).
* 0.13.0 - 23.10.2025
  * Added prereqs-uninstall command.
* 0.12.5 - 22.10.2025
  * Added features to Tesseract OCR installer (Windows).
* 0.12.4 - 16.10.2025
  * Output dependencies installed only if any.
* 0.12.3 - 15.10.2025
  * Fixed Tesseract OCR installer (Windows).
* 0.12.2 - 12.10.2025
  * Fixed Tessaract OCR Manager set PATH.
* 0.12.1 - 09.10.2025
  * Fixed prereqs install in ubuntu installer.
  * Fixed manual method bugs.
* 0.12.0 - 08.10.2025
  * Fixed Virtual Keyboard installer (Debian).
  * Added auto-completion for dkinst installer names and methods. 
* 0.11.1 - 05.10.2025
  * cli - Fixed self sudo restart on Debian.
  * Added installation script for global Debian.
  * Fixed HomeBrew installer (Debian).
  * Fixed xRDP installer (Debian).
* 0.11.0 - 05.10.2025
  * Added Virtual Keyboard enabler for GNOME (Debian).
  * Added VLC installer (Debian).
  * Added VMWare Tools Desktop installer (Debian).
  * Added xRDP installer (Debian).
* 0.10.1 - 02.10.2025
  * Fixed MongoDB installer (Debian).
  * Fixed PyCharm installer (Debian).
* 0.10.0 - 02.10.2025
  * Added BashDB installer (Debian).
  * Added Krusader installer (Debian).
  * Added HomeBrew installer (Debian).
  * Added Admin check under cli.
  * Added dependencies automatic installer under dkinst.
* 0.9.1 - 30.09.2025
  * Fixed MongoDB installer (Debian).
* 0.9.0 - 30.09.2025
  * Added Elasticsearch and Kibana installers (Debian).
* 0.8.2 - 29.09.2025
  * Fixed fibratus installer.
* 0.8.1 - 24.09.2025
  * Added debug.py.
* 0.8.0 - 11.09.2025
  * Added WSL installer (Windows).
* 0.7.2 - 10.09.2025
  * File grabbing fixed with CA certs.
* 0.7.1 - 09.09.2025
  * Minor fixes in MongoDB installer.
* 0.7.0 - 09.09.2025
  * Added MongoDB installer (Windows + Debian).
  * Minor cleaning in Node.js installer.
* 0.6.3 - 09.09.2025
  * Fixed platform recognition.
  * Added Pycharm manual method.
* 0.6.2 - 09.09.2025
  * Fixed msi import globally on non-Windows.
* 0.6.1 - 08.09.2025
  * Fixed Node.js installation on Ubuntu.
* 0.6.0 - 08.09.2025
  * Added Fibratus installer (Windows).
* 0.5.0 - 04.09.2025
  * Added PyWintrace pip from GitHub installer (Windows).
* 0.4.1 - 01.09.2025
  * Admin rights check for Windows on PyCharm installer.
* 0.4.0 - 01.09.2025
  * Added PyCharm (Windows + Debian) installer.
* 0.3.0 - 30.08.2025
  * Added Robocorp framework (Windows) installer and Node.js installer (Windows + Debian).
* 0.2.0 - 29.08.2025
  * Added Robocorp framework installer with some addons for automation.
* 0.1.4 - 29.08.2025
  * Fixed import issue + minor fixes.
* 0.1.0 - 28.08.2025
  * Initial release: tesseract_ocr installer script for Windows.
