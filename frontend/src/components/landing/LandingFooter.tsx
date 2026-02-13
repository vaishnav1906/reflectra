import { Brain, Github, Twitter } from "lucide-react";
import { Link } from "react-router-dom";

export function LandingFooter() {
  return (
    <footer className="border-t border-border bg-card/30">
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12">
          {/* Brand */}
          <div className="md:col-span-2">
            <Link to="/" className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
                <Brain className="w-5 h-5 text-primary" />
              </div>
              <span className="font-semibold text-foreground">Reflectra</span>
            </Link>
            <p className="text-sm text-muted-foreground max-w-sm mb-6">
              A cognitive AI system designed for long-term personalization, 
              memory, and self-reflection. Built with privacy and ethics at its core.
            </p>
            <div className="flex items-center gap-4">
              <a href="#" className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors">
                <Twitter className="w-4 h-4" />
              </a>
              <a href="#" className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors">
                <Github className="w-4 h-4" />
              </a>
            </div>
          </div>

          {/* Product */}
          <div>
            <h4 className="font-semibold text-foreground mb-4">Product</h4>
            <ul className="space-y-3 text-sm text-muted-foreground">
              <li><Link to="/chat" className="hover:text-foreground transition-colors">Chat</Link></li>
              <li><Link to="/personality" className="hover:text-foreground transition-colors">Personality Profile</Link></li>
              <li><Link to="/memory" className="hover:text-foreground transition-colors">Memory Timeline</Link></li>
              <li><Link to="/insights" className="hover:text-foreground transition-colors">Insights</Link></li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="font-semibold text-foreground mb-4">Company</h4>
            <ul className="space-y-3 text-sm text-muted-foreground">
              <li><a href="#" className="hover:text-foreground transition-colors">About</a></li>
              <li><a href="#" className="hover:text-foreground transition-colors">Research</a></li>
              <li><Link to="/settings" className="hover:text-foreground transition-colors">Privacy</Link></li>
              <li><a href="#" className="hover:text-foreground transition-colors">Contact</a></li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground/60">
            © 2025 Reflectra. All rights reserved.
          </p>
          <div className="flex items-center gap-6 text-xs text-muted-foreground/60">
            <a href="#" className="hover:text-muted-foreground transition-colors">Terms of Service</a>
            <a href="#" className="hover:text-muted-foreground transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-muted-foreground transition-colors">Cookie Policy</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
