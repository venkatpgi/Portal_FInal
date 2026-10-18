import Sidebar from "../Sidebar";
import DataQueryBanner from "./DataQueryBanner";
import "../layouts/FormLayout.css";

export default function FormLayout({ children }) {
  return (
    <>
      <Sidebar />

      <div className="form-layout-container">
        <DataQueryBanner />
        {children}
      </div>
    </>
  );
}