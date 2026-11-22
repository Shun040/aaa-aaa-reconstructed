import numpy as np, librosa, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
y, sr = librosa.load('analysis/audio.wav', sr=16000, mono=True)
hop=160
rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=hop)[0]
t = np.arange(len(rms))*hop/sr
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
fig,ax=plt.subplots(2,1,figsize=(24,9),sharex=True)
ax[0].plot(t,20*np.log10(rms+1e-5),lw=.4); ax[0].set_ylabel('dB')
f=librosa.fft_frequencies(sr=sr,n_fft=2048); k=f<2000
ax[1].imshow(20*np.log10(S[k]+1e-4),origin='lower',aspect='auto',extent=[0,t[-1],0,2000],vmin=-40,vmax=30,cmap='magma')
for a in ax: a.set_xticks(np.arange(0,600,20)); a.grid(alpha=.3)
plt.tight_layout(); plt.savefig('analysis/overview.png',dpi=60)
np.save('analysis/rms.npy',rms)
print(len(y)/sr)
