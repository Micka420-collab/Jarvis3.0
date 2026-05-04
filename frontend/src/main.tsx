import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { Admin } from "./admin/Admin";
import "./styles.css";
import "./admin/admin.css";

const isAdmin = location.pathname.startsWith("/admin");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>{isAdmin ? <Admin /> : <App />}</React.StrictMode>,
);
