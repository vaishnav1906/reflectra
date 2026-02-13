import { Link } from "react-router-dom";

export function LandingHeader() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border/50">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3">
          <img
            src="/favicon.ico"
            alt="Reflectra Logo"
            className="h-8 w-8"
          />
          <span className="font-semibold text-foreground">Reflectra</span>
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-8">
          <a href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            How It Works
          </a>
          <Link to="/personality" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Features
          </Link>
          <Link to="/insights" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Insights
          </Link>
        </nav>

        {/* CTA */}
        <Link 
          to="/chat"
          className="px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          Try Reflectra
        </Link>
      </div>
    </header>
  );
}
