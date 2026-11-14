"""Decode observed SunSpec storage controls without retaining stale intent."""
def observed_storage_mode(mode,charge_rate,discharge_rate,requested=None):
    if requested==8 and mode in (1,2,3):return 8  # existing virtual calibration sequence
    if mode==0:return 0
    if mode not in (1,2,3):return None
    if mode&2 and discharge_rate<0:return 4
    if mode&1 and charge_rate<0:return 5
    if requested==4 and mode==2 and discharge_rate==0:return 4
    if requested==5 and mode==1 and charge_rate==0:return 5
    if mode&2 and discharge_rate==0:return 6
    if mode&1 and charge_rate==0:return 7
    return mode
