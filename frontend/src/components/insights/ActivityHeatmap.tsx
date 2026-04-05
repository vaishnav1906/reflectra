import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export const ActivityHeatmap = ({ heatmapData }: { heatmapData: number[][] }) => {
  if (!heatmapData || heatmapData.length === 0) return null;

  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const hours = Array.from({ length: 24 }, (_, i) => i);

  // Find max value to normalize opacity
  let maxCount = 1;
  heatmapData.forEach(row => {
    row.forEach(val => {
      if (val > maxCount) maxCount = val;
    });
  });

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle>Activity Heatmap</CardTitle>
        <CardDescription>When do you reflect the most?</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col space-y-2 select-none">
          <div className="grid grid-cols-[auto_1fr] gap-4 items-center">
            <div className="flex flex-col space-y-1">
              {days.map(d => (
                <div key={d} className="h-6 leading-6 text-xs text-muted-foreground w-8 text-right pr-2">
                  {d}
                </div>
              ))}
            </div>
            
            <div className="flex flex-col space-y-1 overflow-x-auto overflow-y-hidden">
              {heatmapData.map((row, dayIdx) => (
                <div key={`day-${dayIdx}`} className="flex space-x-1">
                  {row.map((count, hourIdx) => {
                    const intensity = count > 0 ? 0.2 + (count / maxCount) * 0.8 : 0;
                    return (
                      <div
                        key={`cell-${dayIdx}-${hourIdx}`}
                        title={`${count} messages at ${hourIdx}:00 on ${days[dayIdx]}`}
                        className={`w-6 h-6 rounded-sm shrink-0 transition-colors duration-300 ${
                          count > 0 ? 'bg-primary cursor-pointer hover:ring-2 hover:ring-white border shadow-inner' : 'bg-muted/20'
                        }`}
                        style={{
                          opacity: count > 0 ? intensity : 1,
                          borderColor: count > 0 ? 'rgba(0,0,0,0.1)' : 'transparent',
                        }}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
          
          <div className="grid grid-cols-[auto_1fr] gap-4 items-center pt-2">
            <div className="w-8"></div>
            <div className="flex justify-between w-max min-w-[max-content] pb-2 text-xs text-muted-foreground">
               <span className="w-6 text-center">12a</span>
               <span className="w-6 text-center ml-[28px*6]">6a</span>
               <span className="w-6 text-center ml-[28px*6]">12p</span>
               <span className="w-6 text-center ml-[28px*6]">6p</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};