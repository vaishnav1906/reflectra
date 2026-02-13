import { Info, Users, Shield } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function PersonaMirrorInfo() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Info className="w-4 h-4" />
          About Persona Mirroring
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            Understanding Persona Mirror Mode
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-4 pt-4">
          <div className="bg-muted/30 rounded-lg p-4">
            <p className="text-sm text-foreground leading-relaxed">
              Persona Mirror Mode reflects how you usually communicate. It does not represent 
              who you are, only how you've been expressing yourself recently.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Users className="w-4 h-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">What it observes</p>
                <p className="text-xs text-muted-foreground">
                  Tone, verbosity, hesitation patterns, and communication style
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Shield className="w-4 h-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">What it does NOT do</p>
                <p className="text-xs text-muted-foreground">
                  It never diagnoses, advises, or claims to know your identity. It observes patterns, not personality.
                </p>
              </div>
            </div>
          </div>

          <p className="text-xs text-muted-foreground/70 pt-2 border-t border-border">
            You can edit or reset your persona data anytime in Settings.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
