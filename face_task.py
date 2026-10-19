"""Find a face anchor for each selected zoom moment. No identity recognition.
Runs separately so OpenCV and decoder memory are released before rendering.
"""
import json,sys
import cv2

def locate(video,moments):
    cv2.setNumThreads(1)
    cascade=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    if cascade.empty():raise RuntimeError('Detector de rosto indisponível.')
    capture=cv2.VideoCapture(str(video),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1])
    if not capture.isOpened():raise RuntimeError('Não foi possível analisar os rostos neste vídeo.')
    found=[]
    try:
        for moment in moments:
            candidates=[]
            # Small snapshots only; no full-rate tracking or external upload.
            for fraction in [.25,.5,.75]:
                capture.set(cv2.CAP_PROP_POS_MSEC,(moment['start']+(moment['end']-moment['start'])*fraction)*1000)
                ok,frame=capture.read()
                if not ok:continue
                h,w=frame.shape[:2];ratio=min(1,640/max(h,w))
                small=cv2.resize(frame,(max(1,round(w*ratio)),max(1,round(h*ratio))))
                gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
                faces=cascade.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(28,28))
                if not len(faces): faces=cascade.detectMultiScale(cv2.equalizeHist(gray),scaleFactor=1.1,minNeighbors=5,minSize=(28,28))
                for x,y,fw,fh in faces:
                    candidates.append((int(fw)*int(fh),(float(x)+fw/2)/small.shape[1],(float(y)+fh/2)/small.shape[0]))
            if candidates:
                _,x,y=max(candidates)
                found.append({**moment,'face_x':float(x),'face_y':float(y)})
    finally:capture.release()
    return found

if __name__=='__main__':
    print(json.dumps(locate(sys.argv[1],json.loads(sys.argv[2]))))
