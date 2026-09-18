import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import EvaluationPage from "./pages/EvaluationPage";
import NewScanPage from "./pages/NewScanPage";
import ReviewPage from "./pages/ReviewPage";
import ScanResultsPage from "./pages/ScanResultsPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<NewScanPage />} />
          <Route path="/scans/:scanId" element={<ScanResultsPage />} />
          <Route path="/scans/:scanId/groups/:groupKey" element={<ReviewPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
