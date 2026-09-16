import Header from "./components/Header";
import ScanForm from "./components/ScanForm";

function App() {
  return (
    <main>
      <Header
        title="Accessibility Fix Assistant"
        subtitle="Scan a public page, review suggested fixes, and keep track of what works."
      />
      <ScanForm />
    </main>
  );
}

export default App;