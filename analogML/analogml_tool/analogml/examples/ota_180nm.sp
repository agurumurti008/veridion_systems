* 5-Transistor OTA — 180nm CMOS Technology
* Topology: differential pair (M1,M2) + current mirror load (M3,M4) + tail (M5)
*
.subckt ota_5t INP INN OUT VDD VSS VBIAS
*
* Differential pair (NMOS)
M1  net1 INP  net3  VSS  nmos_18  W=4u  L=0.18u
M2  net2 INN  net3  VSS  nmos_18  W=4u  L=0.18u
*
* PMOS current-mirror load
M3  net1 net1 VDD   VDD  pmos_18  W=8u  L=0.18u
M4  net2 net1 VDD   VDD  pmos_18  W=8u  L=0.18u
*
* Tail current source
M5  net3 VBIAS VSS  VSS  nmos_18  W=8u  L=0.36u
*
* Miller compensation
Cc  net2 OUT  500f
Rc  OUT  net2 200
*
* Load cap (for simulation)
Cload OUT VSS  2p
*
.ends ota_5t

* Testbench
.subckt tb_ota
Xdut INP INN OUT VDD VSS VBIAS ota_5t
VDD  VDD  0   DC 1.8
VSS  VSS  0   DC 0
VBIAS VBIAS 0 DC 0.6
VIN_CM INP 0 DC 0.9
VIN_DM INP 0 AC 0.5
VIN_DM2 INN 0 AC -0.5
.ends

.op
.ac DEC 100 1 1G
.noise V(OUT) VIN_DM 100

.end
