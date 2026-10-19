import unittest
import numpy as np
from registration_consensus import select


def candidate(seed,x,fitness=.88):
    T=np.eye(4);T[0,3]=x
    return dict(seed=seed,fitness=fitness,rmse=.08,tilt=0.,transform=T.tolist())


class ConsensusTests(unittest.TestCase):
    def test_high_fitness_outlier_does_not_discard_four_agreeing_hints(self):
        rows=[candidate(0,.01),candidate(1,.02),candidate(2,.4,.94),candidate(3,.0),candidate(4,.04)]
        result=select(rows,hint=np.eye(4))
        self.assertTrue(result['accepted']);self.assertEqual(result['supporting_seeds'],[0,1,3,4])
        self.assertNotEqual(result['best']['seed'],2)

    def test_quality_and_hint_bounds_are_required_for_every_supporter(self):
        for key,value in [('fitness',.64),('rmse',.13)]:
            rows=[candidate(i,.01*i) for i in range(4)];rows[3][key]=value
            self.assertFalse(select(rows,hint=np.eye(4))['accepted'])
        self.assertFalse(select([candidate(i,1.+.01*i) for i in range(5)],hint=np.eye(4))['accepted'])

    def test_chained_neighbors_do_not_become_a_four_candidate_consensus(self):
        self.assertFalse(select([candidate(i,.12*i) for i in range(5)],hint=np.eye(4))['accepted'])

    def test_global_requires_three_and_duplicate_seeds_are_rejected(self):
        self.assertTrue(select([candidate(i,.01*i) for i in range(3)])['accepted'])
        self.assertFalse(select([candidate(i,.01*i) for i in range(2)])['accepted'])
        with self.assertRaisesRegex(ValueError,'Duplicate'):select([candidate(0,0),candidate(0,0)])


if __name__=='__main__':unittest.main()
