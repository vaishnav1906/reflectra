import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { 
  Shield, 
  Database, 
  Download, 
  Trash2, 
  Users,
  RefreshCw,
  FileText,
  AlertTriangle,
  Check,
  Loader2,
  Upload
} from "lucide-react";
import { cn } from "@/lib/utils";

const API_BASE = "/api";

type SettingsState = {
  personaMirroring: boolean;
  patternTracking: boolean;
  dailyReflections: boolean;
  shareAnonymousData: boolean;
};

type PersonaSettingKey = "personaMirroring" | "patternTracking" | "dailyReflections";

const DEFAULT_SETTINGS: SettingsState = {
  personaMirroring: true,
  patternTracking: true,
  dailyReflections: true,
  shareAnonymousData: false,
};

export function SettingsPage() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [isLoadingPersonaSettings, setIsLoadingPersonaSettings] = useState(true);
  const [isSavingPersonaSetting, setIsSavingPersonaSetting] = useState<PersonaSettingKey | null>(null);
  const [personaSettingsError, setPersonaSettingsError] = useState<string | null>(null);

  const [isClearDataModalOpen, setIsClearDataModalOpen] = useState(false);
  const [isClearingData, setIsClearingData] = useState(false);
  const [clearDataConfirmation, setClearDataConfirmation] = useState("");

  const [isDeleteAccountModalOpen, setIsDeleteAccountModalOpen] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const [deleteAccountConfirmation, setDeleteAccountConfirmation] = useState("");

  const [isBootstrapModalOpen, setIsBootstrapModalOpen] = useState(false);
  const [bootstrapSummary, setBootstrapSummary] = useState("");
  const [isBootstrapping, setIsBootstrapping] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    const loadPersonaSettings = async () => {
      const userId = localStorage.getItem("user_id");
      if (!userId) {
        if (!isCancelled) {
          setIsLoadingPersonaSettings(false);
        }
        return;
      }

      setIsLoadingPersonaSettings(true);
      setPersonaSettingsError(null);

      try {
        const res = await fetch(`${API_BASE}/user/settings?user_id=${encodeURIComponent(userId)}`);

        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || `HTTP ${res.status}`);
        }

        const data = await res.json();
        const incoming = data?.settings ?? {};

        if (!isCancelled) {
          setSettings((prev) => ({
            ...prev,
            personaMirroring: incoming.persona_mirroring ?? prev.personaMirroring,
            patternTracking: incoming.pattern_tracking ?? prev.patternTracking,
            dailyReflections: incoming.daily_reflections ?? prev.dailyReflections,
          }));
        }
      } catch (err) {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : "Failed to load settings";
          setPersonaSettingsError(msg);
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingPersonaSettings(false);
        }
      }
    };

    void loadPersonaSettings();

    return () => {
      isCancelled = true;
    };
  }, []);

  const handlePersonaToggle = async (key: PersonaSettingKey, checked: boolean) => {
    if (isLoadingPersonaSettings || isSavingPersonaSetting) {
      return;
    }

    const previous = settings;
    const next = { ...settings, [key]: checked };

    setSettings(next);
    setPersonaSettingsError(null);
    setIsSavingPersonaSetting(key);

    try {
      const userId = localStorage.getItem("user_id");
      if (!userId) {
        throw new Error("Missing user session");
      }

      const res = await fetch(`${API_BASE}/user/settings/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          persona_mirroring: next.personaMirroring,
          pattern_tracking: next.patternTracking,
          daily_reflections: next.dailyReflections,
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || `HTTP ${res.status}`);
      }
    } catch (err) {
      setSettings(previous);
      setPersonaSettingsError(err instanceof Error ? err.message : "Unable to save settings");
    } finally {
      setIsSavingPersonaSetting(null);
    }
  };

  const handleBootstrap = async () => {
    if (!bootstrapSummary.trim()) return;
    setIsBootstrapping(true);
    try {
      const userId = localStorage.getItem("user_id");
      if (!userId) return;
      
      const res = await fetch(`${API_BASE}/persona/bootstrap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, summary_text: bootstrapSummary }),
      });
      if (res.ok) {
        setIsBootstrapModalOpen(false);
        setBootstrapSummary("");
        navigate("/app/personality");
      }
    } catch (err) {
      console.error("Failed to bootstrap persona:", err);
    } finally {
      setIsBootstrapping(false);
    }
  };

  const handleClearData = async () => {
    if (clearDataConfirmation !== "CLEAR") return;

    setIsClearingData(true);
    try {
      const userId = localStorage.getItem("user_id");
      if (!userId) return;
      
      const res = await fetch(`${API_BASE}/user/clear-data`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });
      if (res.ok) {
        setIsClearDataModalOpen(false);
        // Refresh UI or show toast
        window.location.reload(); // Simple refresh to fetch fresh persona data
      }
    } catch (err) {
      console.error("Failed to clear user data:", err);
    } finally {
      setIsClearingData(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteAccountConfirmation !== "DELETE") return;
    
    setIsDeletingAccount(true);
    try {
      const userId = localStorage.getItem("user_id");
      if (!userId) return;

      // 2. Add Delay (Protection)
      await new Promise(r => setTimeout(r, 2000));

      const res = await fetch(`${API_BASE}/user/delete-account`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });
      
      if (res.ok) {
        localStorage.clear();
        setIsDeleteAccountModalOpen(false);
        navigate("/");
      }
    } catch (err) {
      console.error("Failed to delete user account:", err);
      setIsDeletingAccount(false); // Only reset if failed. If success it unmounts anyway.
    }
  };

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
                      disabled={isLoadingPersonaSettings || !!isSavingPersonaSetting}
                      checked={settings.personaMirroring}
                      onCheckedChange={(checked) => void handlePersonaToggle("personaMirroring", checked)}
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
                      disabled={isLoadingPersonaSettings || !!isSavingPersonaSetting}
                      checked={settings.patternTracking}
                      onCheckedChange={(checked) => void handlePersonaToggle("patternTracking", checked)}
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
                      disabled={isLoadingPersonaSettings || !!isSavingPersonaSetting}
                      checked={settings.dailyReflections}
                      onCheckedChange={(checked) => void handlePersonaToggle("dailyReflections", checked)}
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
                      <p className="font-medium text-foreground">Import Persona Bootstrap</p>
                      <p className="text-sm text-muted-foreground">
                        Jumpstart your persona profile using a summary from an external AI
                      </p>
                    </div>
                    <Button variant="outline" className="gap-2" onClick={() => setIsBootstrapModalOpen(true)}>
                      <Upload className="w-4 h-4" />
                      Import
                    </Button>
                  </div>
                </div>

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
                      <p className="font-medium text-foreground">Clear All Data</p>
                      <p className="text-sm text-muted-foreground">
                        Delete conversations and persona, keeping your account
                      </p>
                    </div>
                    <Button variant="outline" className="gap-2" onClick={() => setIsClearDataModalOpen(true)}>
                      <RefreshCw className="w-4 h-4" />
                      Clear Data
                    </Button>
                  </div>
                </div>

                <div className="bg-card border border-destructive/30 rounded-xl p-5">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-lg bg-destructive/10 flex items-center justify-center flex-shrink-0">
                      <AlertTriangle className="w-5 h-5 text-destructive" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-foreground mb-1">Delete Account</p>
                      <p className="text-sm text-muted-foreground mb-4">
                        Permanently delete your account and all associated data. This action is permanent and cannot be undone.
                      </p>
                      <Button variant="destructive" size="sm" className="gap-2" onClick={() => setIsDeleteAccountModalOpen(true)}>
                        <Trash2 className="w-4 h-4" />
                        Delete Account
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

      {/* Clear Data Modal */}
      <AlertDialog open={isClearDataModalOpen} onOpenChange={(open) => {
        if (!isClearingData) {
          setIsClearDataModalOpen(open);
          setClearDataConfirmation("");
        }
      }}>
        <AlertDialogContent className="sm:max-w-[425px]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-foreground">Clear All Data</AlertDialogTitle>
            <AlertDialogDescription className="space-y-4">
              <p>
                This will remove all your chats and data. Your account will remain.
              </p>
              <div className="bg-muted border border-border p-3 rounded-md text-muted-foreground text-sm">
                To confirm, please type <strong className="font-bold text-foreground">CLEAR</strong> exactly as shown in the box below:
              </div>
              <Input
                value={clearDataConfirmation}
                onChange={(e) => setClearDataConfirmation(e.target.value)}
                placeholder="CLEAR"
                autoFocus
                disabled={isClearingData}
              />
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              disabled={isClearingData}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleClearData();
              }}
              disabled={clearDataConfirmation !== "CLEAR" || isClearingData}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {isClearingData ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Clearing...
                </>
              ) : (
                "Clear Data"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Account Modal */}
      <AlertDialog open={isDeleteAccountModalOpen} onOpenChange={(open) => {
        if (!isDeletingAccount) {
          setIsDeleteAccountModalOpen(open);
          setDeleteAccountConfirmation("");
        }
      }}>
        <AlertDialogContent className="sm:max-w-[425px]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-destructive">Delete Account</AlertDialogTitle>
            <AlertDialogDescription className="space-y-4">
              <p>
                Are you sure? This action is <strong>permanent and cannot be undone.</strong> 
                It will completely wipe your user account, chat history, metadata, context snapshots, and personalized AI models from our databases immediately.
              </p>
              <div className="bg-destructive/10 border border-destructive/20 p-3 rounded-md text-destructive text-sm">
                To confirm permanent deletion, please type <strong className="font-bold">DELETE</strong> exactly as shown in the box below:
              </div>
              <Input
                value={deleteAccountConfirmation}
                onChange={(e) => setDeleteAccountConfirmation(e.target.value)}
                placeholder="DELETE"
                autoFocus
                disabled={isDeletingAccount}
              />
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              disabled={isDeletingAccount}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleDeleteAccount();
              }}
              disabled={deleteAccountConfirmation !== "DELETE" || isDeletingAccount}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeletingAccount ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete Account"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bootstrap Persona Modal */}
      <Dialog open={isBootstrapModalOpen} onOpenChange={(open) => {
        if (!isBootstrapping) {
          setIsBootstrapModalOpen(open);
          setBootstrapSummary("");
        }
      }}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Import Persona Summary</DialogTitle>
            <DialogDescription>
              Paste a behavioral profile generated by an external AI (like ChatGPT or Claude) to jumpstart your persona.
            </DialogDescription>
          </DialogHeader>
          <div className="my-4">
            <Textarea 
              placeholder="e.g., 'You're hyper-practical. You don't come here to chat...'"
              value={bootstrapSummary}
              onChange={(e) => setBootstrapSummary(e.target.value)}
              className="min-h-[150px] resize-y"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsBootstrapModalOpen(false)} disabled={isBootstrapping}>
              Cancel
            </Button>
            <Button 
              onClick={handleBootstrap} 
              disabled={!bootstrapSummary.trim() || isBootstrapping}
            >
              {isBootstrapping ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Importing...
                </>
              ) : (
                "Import Summary"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
