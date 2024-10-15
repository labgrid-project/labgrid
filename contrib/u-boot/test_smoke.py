# Smoke test for U-Boot
def test_uboot_smoke(u_boot):
    u_boot.run_check("version")
