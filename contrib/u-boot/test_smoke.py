# Smoke test for U-Boot
# Uses the 'u_boot' fixture in conftext.py
def test_uboot_smoke(u_boot):
    u_boot.run_check("version")
