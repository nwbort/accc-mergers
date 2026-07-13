function ErrorMessage({ error }) {
  return (
    <div role="alert" className="text-red-600 p-8 text-center">
      Error: {error}
    </div>
  );
}

export default ErrorMessage;
