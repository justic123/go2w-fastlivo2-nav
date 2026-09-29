import unittest
from callback_drain import drain_ready
class DrainTests(unittest.TestCase):
 def test_burst_serviced_in_order(self):
  pending=list(range(25));received=[]
  def spin():
   if pending:received.append(pending.pop(0))
  self.assertEqual(drain_ready(spin,lambda:0.),32)
  self.assertEqual(received,list(range(25)))
 def test_budget_caps_work(self):
  now=[0.];done=[]
  def spin():done.append(1);now[0]+=.006
  self.assertEqual(drain_ready(spin,lambda:now[0]),3)
if __name__=='__main__':unittest.main()
