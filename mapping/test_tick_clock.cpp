// Standalone simulation and replay: no ROS or robot control.
#include "tick_clock.h"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <sstream>
#include <cassert>
#include <string>
int main(int argc,char**argv){
 if(argc==2){
  TickClock c;std::ifstream f(argv[1]);std::string line;std::getline(f,line);
  unsigned long long w,m,t,prev=0,n=0,duplicates=0;bool have=false;double last=0,minr=1e9,maxr=-1e9,maxlate=0;
  while(std::getline(f,line)){
   if(sscanf(line.c_str(),"%llu,%llu,%llu",&w,&m,&t)!=3)continue;
   if(have&&t==prev){++duplicates;continue;}if(have&&t<prev)return 3;prev=t;have=true;
   const double s=c.update(t,m*1e-9,w*1e-9);if(!c.ready())continue;
   assert(s>last);last=s;const double residual=w*1e-9-s;minr=std::min(minr,residual);maxr=std::max(maxr,residual);
   if(n>30000)maxlate=std::max(maxlate,std::abs(residual));++n;
  }
  std::cout<<std::setprecision(12)<<"{\"samples\":"<<n<<",\"duplicates\":"<<duplicates<<",\"min_residual_s\":"<<minr<<",\"max_residual_s\":"<<maxr<<",\"max_abs_after_60s\":"<<maxlate<<",\"rate_ppm\":"<<c.rate_ppm()<<",\"fits\":"<<c.fits()<<"}\n";return 0;
 }
 for(double ppm:{-80.,0.,30.,80.}){
  TickClock c;double last=0,worst=0;
  for(unsigned long long i=0;i<3600000;++i){
   const double truth=i*.002/(1+ppm*1e-6);
   const double jitter=(i%71)*.000005+(i%1500==0?.03:0);
   const double mono=10000+truth+jitter,wall=1700000000+truth+jitter;
   const double s=c.update(i*2,mono,wall);if(!c.ready())continue;
   assert(s>last);last=s;
   if(i>30000)worst=std::max(worst,std::abs(s-(1700000000+truth)));
  }
  assert(worst<.0015);assert(std::abs(c.rate_ppm()+ppm)<1);
  std::cout<<"two_hour ppm="<<ppm<<" worst_error_s="<<worst<<" fitted="<<c.rate_ppm()<<" PASS\n";
 }
 for(int bad=0;bad<3;++bad){
  TickClock c;for(int i=0;i<600;++i)c.update(i*2,10+i*.002,1000+i*.002);
  bool rejected=false;try{
   if(bad==0)c.update(10,11.2,1001.2);
   if(bad==1)c.update(1200,11.2,1002.2);
   if(bad==2)c.update(1200,12.2,1002.2);
  }catch(const std::runtime_error &){rejected=true;}
  assert(rejected);
 }
 std::cout<<"tick_reset/wall_jump/transport_stall fail-closed PASS\n";
}
