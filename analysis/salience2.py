import numpy as np, librosa
from scipy.ndimage import maximum_filter1d, uniform_filter1d
sr=16000; y,_=librosa.load('analysis/audio.wav',sr=sr,mono=True)
hop=320; n_fft=4096
S=np.abs(librosa.stft(y,n_fft=n_fft,hop_length=hop))
freqs=librosa.fft_frequencies(sr=sr,n_fft=n_fft)
L=np.log1p(S*20)
# spectral whitening: subtract local mean over ~150 Hz
bw=int(150/(sr/n_fft)); W=L-uniform_filter1d(L,bw,axis=0); W=np.maximum(W,0)
# kill mains hum bins (50 Hz multiples up to 1 kHz)
for h in range(1,21):
    W[np.abs(freqs-50*h)<5]*=0.15
Wm=maximum_filter1d(W,3,axis=0)
f0s=np.geomspace(90,1000,260)
def at(fr):
    idx=np.clip(np.round(fr/(sr/n_fft)).astype(int),0,len(freqs)-1); return Wm[idx]
E=np.zeros((len(f0s),W.shape[1])); O=np.zeros_like(E)
for h in range(1,9):
    fr=f0s*h; v=np.zeros_like(E); ok=fr<7500; v[ok]=at(fr[ok]); w=0.85**(h-1)
    if h%2: O+=w*v
    else: E+=w*v
sal=O+E-1.5*np.maximum(0,E-O*1.15)
t=np.arange(W.shape[1])*hop/sr
np.savez_compressed('analysis/sal2.npz',sal=sal,f0s=f0s,t=t,W=W.astype(np.float16) if False else 0)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.figure(figsize=(30,8)); plt.imshow(sal,origin='lower',aspect='auto',extent=[0,t[-1],0,len(f0s)],vmin=0,vmax=np.percentile(sal,99.7),cmap='magma')
yt=[100,150,200,250,300,400,500,600,800,1000]; plt.yticks([np.argmin(abs(f0s-v)) for v in yt],yt); plt.xticks(np.arange(0,600,10)); plt.grid(alpha=.2)
plt.tight_layout(); plt.savefig('analysis/salience2.png',dpi=45)
