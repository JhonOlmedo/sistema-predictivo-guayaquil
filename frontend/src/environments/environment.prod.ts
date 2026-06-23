export const environment = {
  production: true,
  // En producción el frontend lo sirve el mismo backend (misma URL),
  // por eso la API se consume con ruta relativa y no con localhost.
  apiUrl: '/api',
};
