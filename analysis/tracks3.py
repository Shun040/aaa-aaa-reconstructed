import numpy as np, librosa, json
from scipy.ndimage import median_filter
d=np.load('analysis/sal2.npz'); sal,f0s,t=d['sal'],d['f0s'],d['t']
lf=np.log2(f0s); step=lf[1]-lf[0]; T=sal.shape[1]
y,sr=librosa.load('analysis/audio.wav',sr=16000,mono=True)
rms=librosa.feature.rms(y=y,frame_length=640,hop_length=320)[0][:T]; db=20*np.log10(rms+1e-6)
S=np.abs(librosa.stft(y,n_fft=1024,hop_length=320))[:, :T]; fr=librosa.fft_frequencies(sr=16000,n_fft=1024)
tilt=10*np.log10((S[(fr>2000)&(fr<6000)]**2).sum(0)+1e-9)-10*np.log10((S[(fr>100)&(fr<1500)]**2).sum(0)+1e-9)
active=(db>-36)&(t>15.4)&(t<573.3)
G={'U':[(15,155),(50,162),(62,172),(72,205),(85,230),(100,250),(125,268),(140,295),(180,300),(290,310),(300,335),(380,360),(400,330),(575,290)],
   'M':[(15,245),(50,262),(62,280),(72,295),(85,330),(100,390),(125,430),(140,430),(290,440),(380,420),(400,410),(575,380)]}
BAND={'U':0.12,'M':0.25}
def guide(name): g=np.array(G[name]); return 2**np.interp(t,g[:,0],np.log2(g[:,1]))
def viterbi(score, jump_cost=6.0, J=8):
    n=score.shape[0]; back=np.zeros((n,T),dtype=np.int32); idx=np.arange(n); D=score[:,0].copy()
    for k in range(1,T):
        best=np.full(n,-1e9); arg=np.zeros(n,dtype=np.int32)
        for dj in range(-J,J+1):
            src=np.clip(idx-dj,0,n-1); cand=D[src]-jump_cost*abs(dj)*step
            m=cand>best; best[m]=cand[m]; arg[m]=src[m]
        if not active[k]: best=np.full(n,D.max()); arg=np.full(n,D.argmax())
        D=best+score[:,k]; back[:,k]=arg
    p=np.zeros(T,dtype=np.int32); p[-1]=D.argmax()
    for k in range(T-1,0,-1): p[k-1]=back[p[k],k]
    return p
out={}
norm=np.percentile(sal,99,axis=0,keepdims=True)+1e-6
for name in 'UM':
    g=guide(name); dist=np.abs(lf[:,None]-np.log2(g)[None,:])
    score=sal/norm - 4.0*np.maximum(0,dist-BAND[name])
    if name=='M':   # keep off Ulay's fundamental and its octave
        fu=out['U'][0]
        for r in (1,2):
            score-=2.5*(np.abs(lf[:,None]-np.log2(fu*r)[None,:])<0.05)
    p=viterbi(score)
    f=f0s[p]; s=sal[p,np.arange(T)]/norm[0]
    out[name]=(median_filter(f,5),s)
np.savez_compressed('analysis/tracks3.npz',t=t,fU=out['U'][0],sU=out['U'][1],fM=out['M'][0],sM=out['M'][1],db=db,tilt=tilt,active=active)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig,ax=plt.subplots(3,1,figsize=(30,14),sharex=True,gridspec_kw={'height_ratios':[3,1,1]})
ax[0].imshow(sal,origin='lower',aspect='auto',extent=[0,t[-1],0,len(f0s)],vmin=0,vmax=np.percentile(sal,99.7),cmap='gray_r')
yy=lambda f: np.interp(np.log2(f),lf,np.arange(len(f0s)))
ax[0].scatter(t[active],yy(out['M'][0][active]),s=1,c='r'); ax[0].scatter(t[active],yy(out['U'][0][active]),s=1,c='b')
ax[0].set_yticks([yy(v) for v in [100,150,200,300,400,600,800]]); ax[0].set_yticklabels([100,150,200,300,400,600,800])
ax[1].plot(t,median_filter(out['M'][1],25),c='r',lw=.6); ax[1].plot(t,median_filter(out['U'][1],25),c='b',lw=.6); ax[1].set_ylabel('voicing salience')
ax[2].plot(t,median_filter(tilt,25),lw=.6,c='k'); ax[2].set_ylabel('tilt dB (2-6k vs 0.1-1.5k)')
for a in ax: a.set_xticks(np.arange(0,600,10)); a.grid(alpha=.3)
plt.tight_layout(); plt.savefig('analysis/tracks3.png',dpi=45)
