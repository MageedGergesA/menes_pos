# Mezze Hardware Compatibility List (HCL) — S1 §10

**Status: NO HARDWARE CERTIFIED YET.** This is the classification template. A model moves to **CERTIFIED**
only after it passes the relevant §11–15 tests on real hardware and the PASS date + tested release are
recorded. Do not pre-fill CERTIFIED rows. We do **not** claim compatibility with every device.

Classes: **CERTIFIED** (tested & passed) · **COMPATIBLE / LIMITED** (works with documented caveats) ·
**UNTESTED** (expected to work, not verified) · **UNSUPPORTED** (known-bad or explicitly excluded).

Per certified model record: manufacturer · exact model · firmware (if relevant) · connection ·
driver/protocol · installation steps · known limitations · tested release · tested OS/browser · PASS date.

## Receipt printer
| Manufacturer | Model | Firmware | Connection | Protocol | Class | Tested release | PASS date | Notes |
|---|---|---|---|---|---|---|---|---|
| _(reference target)_ | Epson TM-m30 / TM-T88 family (network ePOS) | — | **Ethernet** | ESC/POS / ePOS | UNTESTED | — | — | Preferred reference — known-good with Odoo network ePOS. Verify per §11. |

**UNSUPPORTED by policy:** any **Bluetooth** receipt printer (excluded — do not certify).

## Kitchen printer
| — | (same guidance as receipt printer; network ESC/POS) | — | Ethernet | ESC/POS | UNTESTED | — | — | Optional if branch uses printed kitchen tickets vs KDS. |

## Cash drawer
| — | RJ11/RJ12 drawer driven by the certified receipt printer's DK port | — | via printer | printer kick | UNTESTED | — | — | Document exact drawer↔printer wiring per §12. |

## Waiter tablet
| — | reference Android/iPad at true 1024×768 landscape CSS viewport | OS ver | Wi-Fi | browser | UNTESTED | — | — | Record physical res, CSS viewport, RAM, Wi-Fi band. §13. |

## Cashier workstation
| — | reference x86 mini-PC / laptop, wired Ethernet | — | Ethernet | browser | UNTESTED | — | — | §15. |

## KDS display
| — | reference display + browser device (not the IoT-box UI) | — | Ethernet/Wi-Fi | browser | UNTESTED | — | — | §14. |

## Customer-facing display
| — | reference secondary display / device | — | LAN | browser (`cfd.html`) | UNTESTED | — | — | — |

## Barcode scanner
| — | HID-keyboard-emulation USB scanner | — | USB | HID | UNTESTED | — | — | HID scanners generally work; certify if in scope. |

## Router / access point
| — | business AP with a reliable operations SSID + static/DHCP-reserved Edge IP | — | — | — | UNTESTED | — | — | See networking guidance. |

## UPS
| — | line-interactive UPS sized for Edge server + router + switch (+ printer if required) | — | — | — | UNTESTED | — | — | Minimum runtime target + clean-shutdown policy per §23. |

## Edge server (reference)
| — | x86-64, ≥4 cores, ≥8 GB RAM, SSD, wired Ethernet, supported Linux | — | Ethernet | — | UNTESTED | — | — | Baseline; finalize in requirements. |
