#!/usr/bin/env python3
"""Inventory QML motion for review; candidates are not automatically bugs.
Animations inherited from shared components and data smoothing need manual review.
"""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def inventory(root=ROOT):
 files=sorted((root/'shell').rglob('*.qml'));candidates=[];animated=0
 for path in files:
  if 'plugin' in path.relative_to(root/'shell').parts:continue
  text=path.read_text()
  if re.search(r'\b(?:Anim|CAnim|NumberAnimation|SpringAnimation|MotionSpring|Transition|Behavior)\b',text):animated+=1
  for match in re.finditer(r'\bduration\s*:\s*(\d+)\b',text):
   if int(match.group(1))==0:continue
   candidates.append({'file':str(path.relative_to(root)),'line':text.count('\n',0,match.start())+1,'milliseconds':int(match.group(1)),'fileMentionsReducedMotion':bool(re.search(r'reducedMotion|motionEnabled',text))})
 return {'qmlFiles':len(files),'filesWithDirectMotion':animated,'fixedDurationCandidates':candidates,'note':'Review required: inherited Anim and data smoothing are not missing UI motion.'}
if __name__=='__main__':print(json.dumps(inventory(),ensure_ascii=False,indent=2))
