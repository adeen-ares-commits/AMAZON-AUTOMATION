import sys
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright.sync_api import Browser, Page
from typing import Dict
from profitcal import  get_profitability_metrics
from helium_boot import _find_free_port, _cdp_ready
from main_loop import get_configg

USER_DATA_DIR, PROFILE_DIR, CHROME_PATH, EXT_ID, CDP_PORT = get_configg()
def open_browser(chrome_path, user_data_dir, profile_dir, cdp_port, ext_id, popup_visible=False):
    #open browser
    chrome = Path(chrome_path)
    if not chrome.exists():
        raise FileNotFoundError(f"Chrome not found: {chrome_path}")

    udd = Path(user_data_dir); udd.mkdir(parents=True, exist_ok=True)

    if cdp_port is None:
        cdp_port = _find_free_port()

    if not _cdp_ready(cdp_port):
        print(f"[info] Launching Chrome on port {cdp_port}...")
        args = [
            str(chrome),
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ]
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)

        deadline = time.time() + 25
        while time.time() < deadline and not _cdp_ready(cdp_port):
            time.sleep(0.2)
        if not _cdp_ready(cdp_port):
            raise TimeoutError(f"CDP not ready on 127.0.0.1:{cdp_port}")
        print(f"[info] Chrome launched and CDP ready on {cdp_port}")
    else:
        print(f"[info] Reusing existing Chrome CDP on {cdp_port}")

    cdp_url  = f"http://127.0.0.1:{cdp_port}"
    popup_url = f"chrome-extension://{ext_id}/popup.html"

    print("[info] Connecting Playwright to Chrome...")
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(cdp_url)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    # Open extension popup just to send the message
    popup = ctx.new_page()
    popup.goto(popup_url, wait_until="domcontentloaded")
    print("[info] Opened Helium popup (transient).")

    if not popup_visible:
        try:
            popup.close()
            print("[info] Closed Helium popup tab (minimal UI).")
        except Exception:
            pass
    
    return browser, ctx

urls = [
    "https://www.amazon.de/-/en/Burts-Bees-Lotion-Original-Scent/dp/B0043QASFO/ref=sr_1_1?crid=2AUT5ATDYVYKK&dib=eyJ2IjoiMSJ9.m61-P2W4KfDY1xa8nnBtaSfU87fjhD7fB6zRwvWVDw-RhrjCqecayVH5jKWaCFsFszN6U9f4c2SZ7ANqGrCXz-kek8w6jcpP40mIquSnUd7Jq3axSEiQtIaCWOjEsCk8JfzhQEAUEOqN2GVObWpA4V62UqUsCT_J1Ol0yMbPfkmvqfj3BXqyR_jKQFZSx40A2ni5khRj3DQ2D5p0cfZLEZSjDqc2TUwf3mn6CSu4MjU.cJ0v74ksqrPZwRukklApHHkEGFdYrTjiqh899kPVbJo&dib_tag=se&keywords=lotion&qid=1755640906&rdc=1&s=books&sprefix=lotion%2Cstripbooks%2C537&sr=1-1&th=1",
"https://www.amazon.com.au/COSRX-Good-Morning-Facial-Cleanser/dp/B016NRXO06/ref=sr_1_1?crid=2QG3TQUW0GOSR&dib=eyJ2IjoiMSJ9.lc8v0awtQsliUizPqwkaD42KZfWyo6avH2TtsFG5W3Zz3mDSTG4LrpR4wFmh2w6KqSFjQweCZVKzA7wU5JiK4WHKVvOFyByCT8VQybAhV3PFWayGJex5GacWUti29fWwD8ZR3E9YQMywo6tfYf_kjChC9RD4dCTTixeWs7ZP5WpKZ1t41N7G7K8wODXXon3FdqYnD3am1nQDlyHvZyOxf6MBeEGEym8McCabrSNSsy9pFS7P_XsrDVbQeVzoGBiyAgNHhsbAPxDv9ZK4nObu4SULBKpijhSJbsH6F4SdpG0.hwAzbao_tTF4bKm2-lnZ4GbFQ9XetvuxvTCUtIQIsls&dib_tag=se&keywords=face%2Bwash&qid=1755638367&sprefix=face%2Bwash%2Caps%2C502&sr=8-1&th=1",
"https://www.amazon.ca/PanOxyl-Creamy-Acne-Wash-Peroxide/dp/B09NYTQ2KM/ref=sr_1_1_sspa?crid=24I0T7EQ6KNVY&dib=eyJ2IjoiMSJ9.UILxGSlAJCx5p7pdTFSDVc2HXLX8oK6YBXiRwaL8-DpC5ixIIFd6hduI15ybnJ8Fj1KPBGGRU_2ei-FzC5ET5CEl9uvHb99LGdK9u4NRVkvv9VQOhuoEAOd_99QjMuRCs-DmJph6s1dh06SiG-ZuK-HNW65NMzveEzkKRPH94jztCmg2-LVN6cMz4T_cLHykNYaFxNZGaiFAarRvHBaONkGqe9_BV_zt262TCO5T9cx_FYp4HDSlUiZ2DIxpPhvr-8tkas4yUBJD-Hi2VDXbtQ8sN7YH1belBTpRSAJf_ps.o9msYhcmax8gJPYwuc4I0KsVTxnPY9OzKg4TkwvZlro&dib_tag=se&keywords=face+wash&qid=1755638705&s=beauty&sprefix=face+was%2Cbeauty%2C1067&sr=1-1-spons&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&psc=1",
"https://www.amazon.ae/gp/aw/d/B0D41JK4SZ/?_encoding=UTF8&pd_rd_plhdr=t&aaxitk=8c21ec74134b6529f000d66e21da384f&hsa_cr_id=0&qid=1755638751&sr=1-1-e0fa1fdd-d857-4087-adda-5bd576b25987&ref_=sbx_be_s_sparkle_lsi4d_asin_0_img&pd_rd_w=fQUtD&content-id=amzn1.sym.82b4a379-17da-4039-aebe-5ff2e156261b%3Aamzn1.sym.82b4a379-17da-4039-aebe-5ff2e156261b&pf_rd_p=82b4a379-17da-4039-aebe-5ff2e156261b&pf_rd_r=MPKJJWC3A6A4SZ21BDYB&pd_rd_wg=Xnn35&pd_rd_r=45d9a803-d917-4df2-9fcb-4328aec99929",
"https://www.amazon.co.uk/dp/B08MJZYW8P/?_encoding=UTF8&pd_rd_i=B08MJZYW8P&ref_=sbx_be_s_sparkle_ssd_img&qid=1755638428&pd_rd_w=7ry6l&content-id=amzn1.sym.9d6f7116-ba35-475e-b72d-f446e04d6cf3%3Aamzn1.sym.9d6f7116-ba35-475e-b72d-f446e04d6cf3&pf_rd_p=9d6f7116-ba35-475e-b72d-f446e04d6cf3&pf_rd_r=9W3Q29Y8Y2T2NKS3X5NV&pd_rd_wg=dJxbm&pd_rd_r=5f269e58-e6f1-4d70-938e-0ffc690c3699&pd_rd_plhdr=t&th=1","https://www.amazon.com/Paulas-Choice-Hydrating-Chamomile-Anti-Aging/dp/B00DH209KO/ref=sr_1_1_sspa?crid=5GOZ1YLCJ72P&dib=eyJ2IjoiMSJ9.qCcBDScx-tEi1e--J9aw0C14arfS2QmOqFt-vV9gk0tIvlZI52HwIbav-xcFdzIgiEKS2HgtLCQIRQQWOxkG6YmsmIjEZjR3YwRakfm8H8aol3F-xst-KJjQhBrcpX039HPC6CAXHv9bVO4JPZPdEIc4ncaYuZUgULzwjZmkZ2WhlbD7g2tJwYFXKUYAe-trEbA9qgPhhFZ6dcI4MXtgPilNERxlN4lwHg3N8PqYIOIVM4qvz3rBu46jt6TLfbSr5-R4h983wzU4QVRejLnpzPHjab3blQMZGaqna51vGHg.9jWTNq94nRo2o6TZGxcu5hSl018l838pGRNYqNA2NG4&dib_tag=se&keywords=face+wash&qid=1755638581&sprefix=face+wash%2Caps%2C889&sr=8-1-spons&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&psc=1"
]

browser, ctx = open_browser(CHROME_PATH, USER_DATA_DIR, PROFILE_DIR, CDP_PORT, EXT_ID)

for url in urls:
    for _ in range(5):
        try:
            metrics = get_profitability_metrics(
                browser,
                product_url=url,
                wait_secs=60,
                close_all_tabs_first=False,
                close_others_after_open=True,
            )
            print(metrics, "for url", url)
            break
        except Exception as e:
            print("ERRRRRRRRRRRRRRRRRR",e)







