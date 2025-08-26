# S.T.C.S.
Simple Terminal Communication System
#
**Ne yapabiliyor:**

Terminal üzerinden kullanıcılar arası sohbet.
Takma ad ve IP kontrolü ile aynı IP’den birden fazla client açılmasını veya aynı takma adın kullanılmasını engeller.
Sunucu terminalinden yönetici işlemleri: /kick, /ban, /unban, /say (sohbete sunucu olarak mesaj gönderme), /shutdown.
Client ve server dosyaları internete bağlı ve Python yüklü her cihazda teorik olarak çalışabilir.
Şu ana kadar yapılan testlerde Linux, Windows ve Android (Termux ile, bazı hatalar ileriki sürümlerde düzeltilecektir.) üzerinde çalıştığı onaylanmıştır.
Basit şifre koruması.

**Henüz eksik veya sınırlı:**

Şu anlık yalnızca yerel ağ üzerinde kararlı çalıştığı doğrulanmıştır.
Hatalar ve aksaklıklar olabilir.
Güvenlik önlemleri ilkel düzeydedir.

**Nasıl kullanılır:**

Server dosyasını çalıştırın.
Server dosyasının içindeki sunucu şifresi gibi ayarları yapın.
Client dosyalarını indirip IP ve şifreyi girerek bağlanın (kullanıcı komutlarını öğrenmek için /help komutunu kullanın).
Sunucu terminalinden moderasyon komutlarını (/kick, /ban, /unban, /say, /shutdown) kullanabilirsiniz.
