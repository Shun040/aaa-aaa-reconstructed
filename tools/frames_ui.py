# render the whole page offline, frame by frame, straight into an H.264 part
import asyncio, subprocess, sys
from playwright.async_api import async_playwright
k, a, b = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])   # worker index, frame range [a, b)
async def main():
    ff = subprocess.Popen(["ffmpeg","-v","error","-y","-f","image2pipe","-framerate","25","-c:v","mjpeg","-i","-","-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p",f"/tmp/part_{k}.mp4"], stdin=subprocess.PIPE)
    async with async_playwright() as p:
        br = await p.chromium.launch(); pg = await br.new_page(viewport={"width":1600,"height":900}, device_scale_factor=1.2)
        await pg.goto("http://127.0.0.1:8768/index.html#framesui"); await pg.wait_for_function("!document.getElementById('go').disabled", timeout=60000)
        for i in range(a, b):
            await pg.evaluate(f"renderFrame({i/25})")
            ff.stdin.write(await pg.screenshot(type="jpeg", quality=93))
            if (i - a) % 500 == 0: print(k, i, flush=True)
        await br.close()
    ff.stdin.close(); ff.wait(); print(k, "done", flush=True)
asyncio.run(main())
