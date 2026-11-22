import sys,numpy as np, librosa, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
t0,t1=float(sys.argv[1]),float(sys.argv[2]); u,m=sys.argv[3],sys.argv[4]; out=sys.argv[5]; fmax=float(sys.argv[6]) if len(sys.argv)>6 else 1500
o,_=librosa.load('analysis/audio.wav',sr=16000,mono=True,offset=t0,duration=t1-t0)
U=np.fromfile(u,dtype=np.float32); M=np.fromfile(m,dtype=np.float32)
if len(U)>48000*(t1-t0)*1.02: U=U[int(t0*48000):int(t1*48000)]; M=M[int(t0*48000):int(t1*48000)]
n=min(len(U),len(M)); mix=librosa.resample(U[:n]+M[:n],orig_sr=48000,target_sr=16000)
def spec(x): S=np.abs(librosa.stft(x,n_fft=2048,hop_length=160)); return 20*np.log10(S/ (S.max()+1e-9)+1e-6)
f=librosa.fft_frequencies(sr=16000,n_fft=2048)
fig,ax=plt.subplots(2,2,figsize=(24,10),gridspec_kw={'width_ratios':[3,1]})
for r,(x,n_) in enumerate(((o,'original (mono)'),(mix,'CHIMERA reconstruction'))):
    S=spec(x); k=f<fmax
    ax[r,0].imshow(S[k],origin='lower',aspect='auto',extent=[t0,t1,0,fmax],vmin=-70,vmax=0,cmap='magma'); ax[r,0].set_title(n_)
    ltas=10*np.log10((np.abs(librosa.stft(x,n_fft=2048))**2).mean(1)+1e-12); ax[r,1].plot(f,ltas-ltas.max()); ax[r,1].set_xlim(0,7000); ax[r,1].set_ylim(-70,2); ax[r,1].grid(alpha=.3)
plt.tight_layout(); plt.savefig(out,dpi=50)
def tilt(x):
    S=np.abs(librosa.stft(x,n_fft=1024,hop_length=320)); fr=librosa.fft_frequencies(sr=16000,n_fft=1024)
    a=(S[(fr>2000)&(fr<6000)]**2).sum(0); b=(S[(fr>100)&(fr<1500)]**2).sum(0); m=b>np.percentile(b,40)
    return np.median(10*np.log10(a[m]/b[m]))
print('tilt original %.1f  reconstruction %.1f'%(tilt(o),tilt(mix)))
