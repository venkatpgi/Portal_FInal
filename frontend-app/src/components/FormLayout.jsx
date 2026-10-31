import Sidebar from "../Sidebar";
import DataQueryBanner from "./DataQueryBanner";
import DeathReportBanner from "./DeathReportBanner";
import "../layouts/FormLayout.css";

export default function FormLayout({ children }) {
  return (
    <>
      <Sidebar />

      <div className="form-layout-container">
        <DeathReportBanner />
        <DataQueryBanner />
        {children}
      </div>
    </>
  );
}