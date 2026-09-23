from abaqus import *
from abaqusConstants import *
import visualization, traceback
try:
    vp=session.viewports['Large disbond - U3']
    vp.makeCurrent()
    vp.maximize()
    vp.viewportAnnotationOptions.setValues(state=ON,stateFont='-*-verdana-medium-r-normal-*-12-*-*-*-p-*-*-*')
    vp.odbDisplay.setFrame(step=0,frame=0)
    vp.odbDisplay.contourOptions.setValues(minAutoCompute=OFF,maxAutoCompute=OFF,minValue=-1e-7,maxValue=1e-7)
    vp.view.fitView()
    vp.animationController.setValues(animationType=TIME_HISTORY)
    vp.animationController.play(duration=UNLIMITED)
except Exception:
    open(r'D:/bs_thesis/simulation_reproduction/impact_wave_3d/abaqus/runs/visual_review_20260922/animation_error.txt','w').write(traceback.format_exc())
