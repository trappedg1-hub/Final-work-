import subprocess, sys, os, numpy as np
from PIL import Image
import pyanime4k as a

JOBS = [("sg1","images/f_s2.png"),("sg2","images/f_s1.png"),("sg3","images/sg3_sock_a.png"),("sg4","images/f_s3.png")]

def key(src,dst):
    subprocess.run(["convert",src,"-alpha","on","-fuzz","32%","-fill","none","-draw","matte 0,0 floodfill",dst],check=True)
    subprocess.run(["convert",dst,"-channel","A","-fx","(g>1.20*r && g>1.20*b)?0:a","+channel",
                    "-channel","G","-fx","min(g,max(r,b))","+channel","-trim","+repage",dst],check=True)

def fill_edges(rgb, alpha, iters=40):
    rgb = rgb.copy(); known = alpha > 8
    for _ in range(iters):
        acc = np.zeros_like(rgb); cnt = np.zeros(alpha.shape, np.float32)
        for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
            s = np.roll(np.roll(rgb,dy,0),dx,1); k = np.roll(np.roll(known,dy,0),dx,1)
            acc += s*k[...,None]; cnt += k
        new = (~known) & (cnt>0)
        if not new.any(): break
        rgb[new] = (acc[new]/cnt[new][...,None]).astype(np.uint8)
        known = known | new
    return rgb

for tag,src in JOBS:
    k=f"/tmp/big/{tag}_key.png"; key(src,k)
    im=Image.open(k).convert("RGBA")
    arr=np.array(im); rgb=arr[...,:3]; al=arr[...,3].astype(np.float32)/255.0
    rgb=fill_edges(rgb, arr[...,3])
    al=np.clip((al-0.12)/0.88,0,1)
    Image.fromarray(rgb).save(f"/tmp/big/{tag}_rgb.png")
    a.upscale_images([f"/tmp/big/{tag}_rgb.png"],[f"/tmp/big/{tag}_rgb4.png"],factor=4.0,model_name="acnet-gan",processor_type="cpu")
    big=Image.open(f"/tmp/big/{tag}_rgb4.png").convert("RGB")
    A=Image.fromarray((al*255).astype(np.uint8)).resize(big.size, Image.LANCZOS)
    m=big.copy(); m.putalpha(A)
    m.save(f"assets/master/art_day1_{tag}_4x.png")
    m.save(f"assets/art_day1_{tag}.webp","WEBP",quality=92,method=6)
    print(tag, m.size, round(os.path.getsize(f"assets/art_day1_{tag}.webp")/1e6,2),"MB webp",
          round(os.path.getsize(f"assets/master/art_day1_{tag}_4x.png")/1e6,2),"MB master")

# --- final normalisation: common 2100x4600 canvas, centred, feet on the bottom line ---
def normalise(master_png, out_webp, CW=2100, CH=4600, quality=92):
    from PIL import Image
    im = Image.open(master_png).convert("RGBA")
    if im.height != CH:
        im = im.resize((round(im.width * CH / im.height), CH), Image.LANCZOS)
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((CW - im.width) // 2, CH - im.height))
    canvas.save(out_webp, "WEBP", quality=quality, method=6)
