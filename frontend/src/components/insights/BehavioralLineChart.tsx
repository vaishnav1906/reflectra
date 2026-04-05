import React from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { format } from 'date-fns';

export const BehavioralLineChart = ({ data, view }: { data: any[], view: string }) => {
  if (!data || data.length === 0) return null;

  const formatXAxis = (tickItem: string) => {
    const date = new Date(tickItem);
    return view === 'day' ? format(date, 'ha') : view === 'week' ? format(date, 'EEE') : format(date, 'dd MMM');
  };

  return (
    <Card className="col-span-full h-full">
      <CardHeader>
        <CardTitle>Behavioral Trends over Time</CardTitle>
        <CardDescription>Visualizing emotional intensity and verbosity</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorEmotion" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="timestamp" tickFormatter={formatXAxis} tick={{fill: '#9ca3af', fontSize: 12}} />
              <YAxis yAxisId="left" orientation="left" stroke="#10b981" />
              <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" domain={[0, 1]} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }}
                itemStyle={{ color: '#fff' }}
                labelFormatter={formatXAxis}
              />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="total_tokens"
                name="Verbosity (Tokens)"
                stroke="#10b981"
                fillOpacity={1}
                fill="url(#colorTokens)"
              />
              <Area
                yAxisId="right"
                type="monotone"
                dataKey="emotional_intensity"
                name="Emotional Intensity"
                stroke="#f59e0b"
                fillOpacity={1}
                fill="url(#colorEmotion)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
};