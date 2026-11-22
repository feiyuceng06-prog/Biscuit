let connection;
function database() {
  if (!connection)
    connection = new Promise((resolve, reject) => {
      const req = indexedDB.open('biscuit-office', 1);
      req.onupgradeneeded = () => req.result.createObjectStore('presentations');
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => {
        connection = null;
        reject(req.error);
      };
    });
  return connection;
}
export async function draft(workspace, value) {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('presentations', value ? 'readwrite' : 'readonly');
    const store = tx.objectStore('presentations');
    const request = value ? store.put(value, workspace) : store.get(workspace);
    tx.oncomplete = () => resolve(request.result);
    tx.onabort = () => reject(tx.error || Error('草稿存储失败'));
  });
}
