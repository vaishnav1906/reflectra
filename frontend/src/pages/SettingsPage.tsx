import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { 
  Shield, 
  Database, 
  Download, 
  Trash2, 
  Users,
  RefreshCw,
  FileText,
  AlertTriangle,
  Check
} from "lucide-react";
import { cn } from "@/lib/utils";

export function SettingsPage() {
  const [settings, setSettings] = useState({
    personaMirroring: true,
    patternTracking: true,
    dailyReflections: true,
    shareAnonymousData: false,
  });

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 border-b border-border">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Manage your persona data and preferences
          </p>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8">
          <div className="max-w-2xl mx-auto space-y-8">
            {/* Persona Controls */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Users className="w-5 h-5 text-primary" />
                <h2 className="text-lg font-semibold text-foreground">Persona Settings</h2>
              </div>

              <div className="bg-card border border-border rounded-xl divide-y divide-border">
                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Persona Mirroring</p>
                      <p className="text-sm text-muted-foreground">
                        Allow Reflectra to reflect your communication style
                      </p>
                    </div>
                    <Switch
                      checked={settings.personaMirroring}
                      onCheckedChange={(checked) => 
                        setSettings({ ...settings, personaMirroring: checked })
                      }
                    />
                  </div>
                </div>

                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Pattern Tracking</p>
                      <p className="text-sm text-muted-foreground">
                        Track communication patterns over time
                      </p>
                    </div>
                    <Switch
                      checked={settings.patternTracking}
                      onCheckedChange={(checked) => 
                        setSettings({ ...settings, patternTracking: checked })
                      }
                    />
                  </div>
                </div>

                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Daily Reflections</p>
                      <p className="text-sm text-muted-foreground">
                        Show daily reflection input in chat
                      </p>
                    </div>
                    <Switch
                      checked={settings.dailyReflections}
                      onCheckedChange={(checked) => 
                        setSettings({ ...settings, dailyReflections: checked })
                      }
                    />
                  </div>
                </div>
              </div>
            </section>

            {/* Privacy Section */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-5 h-5 text-primary" />
                <h2 className="text-lg font-semibold text-foreground">Privacy</h2>
              </div>

              <div className="bg-card border border-border rounded-xl divide-y divide-border">
                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Data Encryption</p>
                      <p className="text-sm text-muted-foreground">
                        All data encrypted at rest and in transit
                      </p>
                    </div>
                    <div className="flex items-center gap-2 text-green-500">
                      <Check className="w-4 h-4" />
                      <span className="text-sm font-medium">Active</span>
                    </div>
                  </div>
                </div>

                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Anonymous Usage Data</p>
                      <p className="text-sm text-muted-foreground">
                        Help improve Reflectra with anonymized metrics
                      </p>
                    </div>
                    <Switch
                      checked={settings.shareAnonymousData}
                      onCheckedChange={(checked) => 
                        setSettings({ ...settings, shareAnonymousData: checked })
                      }
                    />
                  </div>
                </div>
              </div>
            </section>

            {/* Data Management Section */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Database className="w-5 h-5 text-primary" />
                <h2 className="text-lg font-semibold text-foreground">Data Management</h2>
              </div>

              <div className="space-y-4">
                <div className="bg-card border border-border rounded-xl p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Export Persona Summary</p>
                      <p className="text-sm text-muted-foreground">
                        Download a text summary of your persona profile
                      </p>
                    </div>
                    <Button variant="outline" className="gap-2">
                      <FileText className="w-4 h-4" />
                      Export
                    </Button>
                  </div>
                </div>

                <div className="bg-card border border-border rounded-xl p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Reset Persona Data</p>
                      <p className="text-sm text-muted-foreground">
                        Clear all learned patterns and start fresh
                      </p>
                    </div>
                    <Button variant="outline" className="gap-2">
                      <RefreshCw className="w-4 h-4" />
                      Reset
                    </Button>
                  </div>
                </div>

                <div className="bg-card border border-destructive/30 rounded-xl p-5">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-lg bg-destructive/10 flex items-center justify-center flex-shrink-0">
                      <AlertTriangle className="w-5 h-5 text-destructive" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-foreground mb-1">Delete All Data</p>
                      <p className="text-sm text-muted-foreground mb-4">
                        Permanently delete all conversations, persona data, and reflections. This cannot be undone.
                      </p>
                      <Button variant="destructive" size="sm" className="gap-2">
                        <Trash2 className="w-4 h-4" />
                        Delete Everything
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Version Info */}
            <div className="text-center py-6 border-t border-border">
              <p className="text-xs text-muted-foreground">
                Reflectra v1.0 • Your data stays with you
              </p>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
