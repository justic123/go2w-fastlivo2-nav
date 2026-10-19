#pragma once
// Map hardware milliseconds onto the source host's monotonic clock. Receipt
// time is a noisy observation, NOT a replacement timestamp for every sample.
#include <algorithm>
#include <cmath>
#include <deque>
#include <stdexcept>
#include <vector>

class TickClock {
 struct Point { double x,y; };
 std::vector<double> initial;
 std::deque<Point> samples;
 double origin=0, wall_offset=0, first_tick=0, last_x=0, last_y=0;
 double rate=1, intercept=0, fitted_intercept=0, last_fit=0, last_sample=-1;
 bool started=false, ready_=false;
 unsigned fits_=0;
 static double median(std::vector<double> v) {
  std::sort(v.begin(),v.end());const auto n=v.size();
  return n%2?v[n/2]:(v[n/2-1]+v[n/2])*.5;
 }
 void fit(double x) {
  if(x-last_fit<1 || samples.size()<40)return;
  last_fit=x;std::vector<double> slopes;
  for(size_t i=0;i<samples.size();++i)for(size_t j=i+1;j<samples.size();++j) {
   const double dt=samples[j].x-samples[i].x;
   if(dt>=10)slopes.push_back((samples[j].y-samples[i].y)/dt);
  }
  if(slopes.empty())return;
  const double candidate=median(slopes);
  // Do not interpret a transport stall as an arbitrarily fast/slow oscillator.
  if(std::abs(candidate-1)>200e-6)return;
  std::vector<double> offsets;
  for(const auto &p:samples)offsets.push_back(p.y-candidate*p.x);
  rate=candidate;fitted_intercept=median(offsets);++fits_;
 }
public:
 bool ready()const{return ready_;}
 double rate_ppm()const{return (rate-1)*1e6;}
 unsigned fits()const{return fits_;}
 double initial_anchor()const{return origin+wall_offset+intercept;}
 double update(unsigned long long tick,double mono,double wall) {
  if(!std::isfinite(mono)||!std::isfinite(wall))throw std::runtime_error("Nonfinite source clock");
  if(!started){started=true;origin=mono;wall_offset=wall-mono;first_tick=tick;}
  const double x=(double(tick)-first_tick)*.001,y=mono-origin;
  if(std::abs((wall-mono)-wall_offset)>.1)throw std::runtime_error("Host wall/monotonic offset changed over 100ms: reinitialize");
  if(x<=last_x && !initial.empty())throw std::runtime_error("Tick reset/duplicate: reinitialize");
  if(x-last_sample>=.5){samples.push_back({x,y});last_sample=x;}
  while(!samples.empty() && x-samples.front().x>60)samples.pop_front();
  if(!ready_){
   initial.push_back(y-x);last_x=x;
   if(initial.size()<500)return 0;
   intercept=median(initial);fitted_intercept=intercept;
   last_y=intercept+x;ready_=true;
  }else{
   fit(x);
   const double dt=x-last_x,predicted=last_y+rate*dt;
   const double error=fitted_intercept+rate*x-predicted;
   // Slew at <=200us/s. No timestamp discontinuity when the fitted clock changes.
   last_y=predicted+std::max(-200e-6*dt,std::min(200e-6*dt,error));
   last_x=x;
  }
  if(std::abs(y-last_y)>.5)throw std::runtime_error("Tick/host alignment exceeds 500ms guard");
  return origin+wall_offset+last_y;
 }
};
