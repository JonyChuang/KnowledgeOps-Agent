import { useAppStore } from "../store/app-store";
import { AgentPage } from "./agent/AgentPage";
import { CreateTicketPage } from "./tickets/CreateTicketPage";
import { DashboardPage } from "./dashboard/DashboardPage";
import { DocumentsPage } from "./knowledge/DocumentsPage";
import { GraphPage } from "./knowledge/GraphPage";
import { KnowledgePage } from "./knowledge/KnowledgePage";
import { NotificationsPage } from "./engagement/NotificationsPage";
import { PersonalLibraryPage } from "./engagement/PersonalLibraryPage";
import { SearchPage } from "./engagement/SearchPage";
import { ProfilePage } from "./profile/ProfilePage";
import { ServiceDeskPage } from "./tickets/ServiceDeskPage";
import { TicketsPage } from "./tickets/TicketsPage";
import { UserManagementPage } from "./profile/UserManagementPage";

export function ViewRouter() {
  const view = useAppStore((state) => state.activeView);
  switch (view) {
    case "agent": return <AgentPage />;
    case "search": return <SearchPage />;
    case "tickets": return <TicketsPage />;
    case "create-ticket": return <CreateTicketPage />;
    case "service-desk": return <ServiceDeskPage />;
    case "knowledge": return <KnowledgePage />;
    case "documents": return <DocumentsPage />;
    case "graph": return <GraphPage />;
    case "notifications": return <NotificationsPage />;
    case "personal-library": return <PersonalLibraryPage />;
    case "user-management": return <UserManagementPage />;
    case "profile": return <ProfilePage />;
    default: return <DashboardPage />;
  }
}
