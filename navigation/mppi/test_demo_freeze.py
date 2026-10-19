import unittest
from demo_freeze import encode_grid
class GridTests(unittest.TestCase):
 def test_unknown_is_not_free_and_inflation_is_recomputed(self):
  self.assertEqual(encode_grid([-1,0,98,99,100,1],3,2),bytes([254,0,254,205,254,254]))
 def test_inflated_band_is_not_baked_into_obstacle(self):
  # A lethal obstacle surrounded by inscribed and softer costs saves one cell only.
  out=encode_grid([0,98,99,100,99,98,0],7,1)
  self.assertEqual(list(out),[254,254,254,0,254,254,254]);self.assertEqual(out.count(0),1)
 def test_no_free_map_is_rejected(self):
  with self.assertRaises(ValueError):encode_grid([-1,100],2,1)
 def test_invalid_cost_is_rejected(self):
  with self.assertRaises(ValueError):encode_grid([0,101],2,1)
if __name__=='__main__':unittest.main()
