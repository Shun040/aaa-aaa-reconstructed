import asyncio, os, json
from playwright.async_api import async_playwright
SEG=[("A",509.0,512.4),("B",0.0,7.1),("C",19.0,28.2),("D",40.0,50.6),("E",515.6,526.6),("F",150.0,158.0),("G",567.3,576.5)]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":1080,"height":1000})
        await pg.goto("http://127.0.0.1:8768/index.html#frames"); await pg.wait_for_function("!document.getElementById('go').disabled", timeout=60000)
        await pg.evaluate("document.getElementById('start').style.display='none'")
        for name,t0,t1 in SEG:
            d=f"/tmp/frames/{name}"; os.makedirs(d,exist_ok=True)
            n=int(round((t1-t0)*25))
            for i in range(n):
                await pg.evaluate(f"renderFrame({t0+i/25})")
                await pg.screenshot(path=f"{d}/{i:04d}.png")
            print(name,n,flush=True)
        await b.close()
asyncio.run(main())
