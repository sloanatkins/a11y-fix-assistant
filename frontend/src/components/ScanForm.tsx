function ScanForm() {
  return (
    <form>
      <label htmlFor="page-url">Page URL</label>
      <input
        id="page-url"
        name="url"
        type="url"
        placeholder="https://www.example.com"
        required
      />
      <button type="submit">Scan page</button>
    </form>
  );
}

export default ScanForm;