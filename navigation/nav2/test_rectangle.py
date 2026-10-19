import unittest,math
from motion_policy import swept_clear
class RectangleTests(unittest.TestCase):
 def grid(self):return ([0]*40000,200,200,.02,-2,-2)
 def obstacle(self,g,x,y,value=100):g[0][int((y+2)/.02)*200+int((x+2)/.02)]=value
 def test_clear_corridor_and_side_contact(self):
  g=self.grid()
  for x in range(200):g[0][int((.38+2)/.02)*200+x]=100;g[0][int((-.38+2)/.02)*200+x]=100
  swept_clear(g,(0,0,0),(.1,0,0))
  with self.assertRaises(ValueError):swept_clear(g,(0,0,math.pi/2),(0,0,0))
 def test_rotated_corner_and_unknown(self):
  for v in [-1,100]:
   g=self.grid();self.obstacle(g,.11,.47,v)
   swept_clear(g,(0,0,0),(0,0,0))
   with self.assertRaises(ValueError):swept_clear(g,(0,0,math.pi/4),(0,0,0))
 def test_rotation_sweep(self):
  g=self.grid();self.obstacle(g,.39,.36)
  swept_clear(g,(0,0,0),(0,0,0))
  with self.assertRaises(ValueError):swept_clear(g,(0,0,0),(0,0,.1))
 def test_high_speed_rotation_sweep(self):
  for w in [-.8,.8]:
   g=self.grid();swept_clear(g,(0,0,0),(0,0,w))
   self.obstacle(g,.3,.4 if w>0 else -.4)
   swept_clear(g,(0,0,0),(0,0,0))
   with self.assertRaises(ValueError):swept_clear(g,(0,0,0),(0,0,w))

 def test_ten_cm_clearance_on_sides_and_front(self):
  # Obstacles outside the physical body but inside its reserved 10 cm are blocked.
  for x,y in [(0,.28),(0,-.28),(.44,0),(-.44,0)]:
   g=self.grid();self.obstacle(g,x,y)
   with self.assertRaises(ValueError):swept_clear(g,(0,0,0),(0,0,0))
  for x,y in [(0,.36),(0,-.36),(.52,0),(-.52,0)]:
   g=self.grid();self.obstacle(g,x,y);swept_clear(g,(0,0,0),(0,0,0))
