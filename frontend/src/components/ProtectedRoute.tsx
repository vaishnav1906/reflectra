import { Navigate } from "react-router-dom";
import { ReactNode } from "react";

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const userId = localStorage.getItem("user_id");
  
  if (!userId) {
    return <Navigate to="/" replace />;
  }
  
  return <>{children}</>;
}
