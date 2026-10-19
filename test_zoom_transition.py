"""Measure actual FFmpeg output frames, including abrupt zoom entry/exit."""
import subprocess
from app import zoom_filter,EditOptions
from pydantic import ValidationError

def widths(transition,moments=None):
    vf=zoom_filter(moments or [{'start':1,'end':2}],180,320,50,transition)
    raw=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=black:s=180x320:r=30:d=3,drawbox=x=70:y=100:w=40:h=120:c=white:t=fill','-vf',vf+',format=gray','-threads','1','-f','rawvideo','-pix_fmt','gray','-'])
    size=180*320
    return [sum(v>200 for v in raw[i*size+160*180:i*size+161*180]) for i in range(90)]
hard=widths('cut');smooth=widths('smooth')
assert 38<=hard[29]<=42 and 58<=hard[30]<=62 and abs(hard[30]-hard[59])<=2 and 38<=hard[60]<=42,hard[28:62]
assert smooth[30]<hard[30]-10 and smooth[33]<smooth[45] and smooth[57]<smooth[45] and abs(smooth[45]-hard[45])<=2
# Adjacent moments must not sum zoom strengths on the shared boundary.
adjacent=widths('cut',[{'start':1,'end':1.5},{'start':1.5,'end':2}]);assert abs(adjacent[45]-hard[45])<=2
assert EditOptions().zoom_transition=='smooth'
try:EditOptions(zoom_transition='invalid');raise AssertionError('invalid transition accepted')
except ValidationError:pass
print({'PASS':True,'cut_widths_before_entry_peak_exit':[hard[i] for i in [29,30,45,59,60]],'smooth_widths':[smooth[i] for i in [30,33,45,57,60]],'adjacent_boundary':True})
