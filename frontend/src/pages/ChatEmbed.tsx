import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import ChatWidget from "@/components/ChatWidget";

export default function ChatEmbed() {
  const { token } = useParams();
  const [site, setSite] = useState(null);
  useEffect(() => { axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/public/site/${token}`).then(r => setSite(r.data)).catch(() => setSite({ app: { name: "Assistant" }, theme: { primary: "#F97316", mode: "light" } })); }, [token]);
  useEffect(() => { document.documentElement.style.background = "transparent"; document.body.style.background = "transparent"; }, []);
  if (!site) return null;
  return <div style={{ background: "transparent", minHeight: "100vh" }} data-testid="chat-embed-page"><ChatWidget token={token} brand={site.app.name} accent={site.theme?.primary || "#F97316"} light={site.theme?.mode !== "dark"} /></div>;
}
